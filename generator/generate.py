from __future__ import annotations
import random
from parser.schema import Trace, Turn, ToolCall
from generator.tools import INTENTS, correct_tool
from generator.phrasings import phantom_claims, phrasings_for, USER_PHRASINGS

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

def _phantom(cid, intent, rng, held_out) -> Trace:
    err = "txn_not_found" if intent == "dispute_charge" else "billing_active"
    call = ToolCall(correct_tool(intent), {a: f"{a}_val" for a in INTENTS[intent]["args"]},
                    {"success": False, "error": err}, "ok", 220, None)
    return Trace(cid, intent, intent, ["phantom_action"], [Turn("user", rng.choice(USER_PHRASINGS[intent])),
                 Turn("agent", rng.choice(phantom_claims(intent, held_out)), [call])], dict(_SIGNALS), True, None)

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

def generate_dataset(n=1000, clean_ratio=0.8, held_out=False, seed=0) -> list[Trace]:
    rng = random.Random(seed)
    intents = list(INTENTS)
    n_clean = int(n * clean_ratio)
    n_hard = int(n * 0.08)
    n_fail = n - n_clean
    out: list[Trace] = []
    for i in range(n_clean - n_hard):
        out.append(_clean(f"c_{i}", rng.choice(intents), rng))
    for i in range(n_hard):
        out.append(_hard_negative(f"h_{i}", rng, held_out))
    makers = [lambda cid: _phantom(cid, "dispute_charge", rng, held_out),
              lambda cid: _phantom(cid, "cancel_subscription", rng, held_out),
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
