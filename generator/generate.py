from __future__ import annotations
import random
from parser.schema import Trace, Turn, ToolCall
from generator.tools import INTENTS, correct_tool
from generator.phrasings import (phantom_claims, phantom_euphemisms, phrasings_for,
                                 grounded_policy, USER_PHRASINGS)

_SIGNALS = {"user_reask": False, "user_correction": False, "abandoned": False}

def _clean(cid, intent, rng) -> Trace:
    call = ToolCall(correct_tool(intent), {a: f"{a}_val" for a in INTENTS[intent]["args"]},
                    {"success": True}, "ok", 180, None)
    return Trace(cid, intent, intent, [], [Turn("user", rng.choice(USER_PHRASINGS[intent])),
                 Turn("agent", "Done — all set.", [call])], dict(_SIGNALS), True, None)

def _hard_negative(cid, rng, held_out) -> Trace:
    intent = "dispute_charge"
    claim = rng.choice(phantom_claims(intent, held_out))
    call = ToolCall("file_dispute", {"txn_id": "txn_val"}, {"success": True, "dispute_id": "d_1"}, "ok", 210, None)
    t = Trace(cid, intent, intent, [], [Turn("user", rng.choice(USER_PHRASINGS[intent])),
              Turn("agent", claim, [call])], dict(_SIGNALS), True, None)
    t.is_hard_negative = True
    return t

def _phantom(cid, intent, rng, held_out, euphemistic=False) -> Trace:
    # euphemistic=True → agent asserts success with NO CONFIRM_WORDS token (breaks the tautology:
    # heuristics-only baseline and StubJudge both miss these). Ground truth is still phantom_action:
    # the tool failed (success:False) yet the agent claims completion.
    err = "txn_not_found" if intent == "dispute_charge" else "billing_active"
    call = ToolCall(correct_tool(intent), {a: f"{a}_val" for a in INTENTS[intent]["args"]},
                    {"success": False, "error": err}, "ok", 220, None)
    claims = phantom_euphemisms(intent, held_out) if euphemistic else phantom_claims(intent, held_out)
    return Trace(cid, intent, intent, ["phantom_action"], [Turn("user", rng.choice(USER_PHRASINGS[intent])),
                 Turn("agent", rng.choice(claims), [call])], dict(_SIGNALS), True, None)

def _grounded_clean(cid, rng, held_out) -> Trace:
    # Grounded hard-negative for ungrounded: retrieval score ABOVE RETRIEVAL_TAU (0.5) and the agent's
    # factual claim MATCHES the retrieved chunk, so a correct detector must STAY SILENT. Clean-labeled
    # (injected_labels=[]) → enters the clean pool. Vary the day-count and score so it isn't one pattern.
    days = rng.choice([30, 45, 60, 90, 120])
    score = round(rng.uniform(0.62, 0.95), 2)          # comfortably above tau=0.5
    chunk, claim = grounded_policy(days, held_out)
    call = ToolCall("policy_search", {"query": "dispute window"}, {"success": True}, "ok", 150,
                    retrieved=[{"chunk_id": "k1", "text": chunk, "score": score}])
    return Trace(cid, "policy_question", "policy_question", [],
                 [Turn("user", rng.choice(USER_PHRASINGS["policy_question"])),
                  Turn("agent", claim, [call])], dict(_SIGNALS), True, None)

def _ungrounded(cid, rng, held_out) -> Trace:
    intent = "policy_question"
    call = ToolCall("policy_search", {"query": "dispute window"}, {"success": True}, "ok", 150,
                    retrieved=[{"chunk_id": "k1", "text": "the dispute window is 90 days", "score": 0.2}])
    return Trace(cid, intent, intent, ["ungrounded"], [Turn("user", rng.choice(USER_PHRASINGS[intent])),
                 Turn("agent", rng.choice(phrasings_for("ungrounded", held_out)), [call])], dict(_SIGNALS), True, None)

def _misrouted(cid, rng) -> Trace:
    intent, routed = "dispute_charge", "request_refund"          # customer wants a dispute; agent did a refund
    call = ToolCall("issue_refund", {"txn_id": "txn_val", "amount": "amount_val"}, {"success": True}, "ok", 130, None)
    return Trace(cid, intent, routed, ["misrouting"], [Turn("user", rng.choice(USER_PHRASINGS[intent])),
                 Turn("agent", "Your refund is processed.", [call])], dict(_SIGNALS), True, None)

# Fraction of phantom positives whose completion claim is confirm-word-free (euphemistic).
# These are true positives that the CONFIRM_WORDS heuristic and StubJudge MISS, so heuristics-only
# recall drops below 1.0 while staying above the 0.8 regression floor. ~1-in-7 phantoms.
_EUPHEMISM_EVERY = 7

def generate_dataset(n=1000, clean_ratio=0.8, held_out=False, seed=0) -> list[Trace]:
    rng = random.Random(seed)
    intents = list(INTENTS)
    n_clean = int(n * clean_ratio)          # total clean traces (injected_labels == [])
    n_hard = int(n * 0.08)                   # failure-ish-but-fine hard negatives (tool succeeded)
    n_grounded = int(n * 0.06)               # grounded clean hard-negs for ungrounded (score>tau, claim matches)
    n_fail = n - n_clean                     # true positives across modes
    n_plain_clean = n_clean - n_hard - n_grounded
    out: list[Trace] = []
    for i in range(n_plain_clean):
        out.append(_clean(f"c_{i}", rng.choice(intents), rng))
    for i in range(n_hard):
        out.append(_hard_negative(f"h_{i}", rng, held_out))
    for i in range(n_grounded):
        out.append(_grounded_clean(f"g_{i}", rng, held_out))
    # Count phantom emissions so a deterministic minority becomes euphemistic (confirm-word-free).
    phantom_seen = 0
    def _make_phantom(cid, intent):
        nonlocal phantom_seen
        euph = (phantom_seen % _EUPHEMISM_EVERY) == (_EUPHEMISM_EVERY - 1)
        phantom_seen += 1
        return _phantom(cid, intent, rng, held_out, euphemistic=euph)
    makers = [lambda cid: _make_phantom(cid, "dispute_charge"),
              lambda cid: _make_phantom(cid, "cancel_subscription"),
              lambda cid: _ungrounded(cid, rng, held_out),
              lambda cid: _misrouted(cid, rng)]
    for i in range(n_fail):
        out.append(makers[i % 4](f"f_{i}"))
    rng.shuffle(out)
    return out

def composition(traces) -> dict:
    total = len(traces)
    clean = sum(1 for t in traces if not t.injected_labels)
    by_mode: dict[str, int] = {}
    for t in traces:
        for lbl in t.injected_labels:
            by_mode[lbl] = by_mode.get(lbl, 0) + 1
    return {"total": total, "clean": clean, "clean_fraction": clean / total, "by_mode": by_mode}
