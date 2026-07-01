# Silent-Failure Detector v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v1 offline detector — generate labeled synthetic support-agent traces, detect phantom-action / ungrounded / misrouting failures with a hybrid heuristics + LLM-judge design, and produce an honest eval plus a ranked report with one measured guardrail loop. Published numbers come from a real `ClaudeJudge` pass; CI runs key-free on a deterministic `StubJudge`.

**Architecture:** A stdlib-only pipeline — `generator → parser(redact) → features → detector-registry → group-by → reports` — with an `eval` harness as the spine. Detectors implement a common `Detector` protocol and live in a registry so v2 (monitor loop) and v3 (inline verifier) add modes without editing call sites. The LLM judge sits behind a `Judge` protocol (`StubJudge` for CI, `ClaudeJudge` for real numbers). Ground truth comes only from generator `injected_labels`.

**Tech Stack:** Python 3.12, `pytest`. Core spine uses the standard library only. `anthropic` (optional `[judge]` extra) for the real judge; `scikit-learn` (optional `[calibrate]` extra) is a *future* upgrade — v1 calibration is stdlib.

## Global Constraints

- **Interpreter:** use `C:\Users\antho\AppData\Local\Programs\Python\Python312\python.exe` (the Windows Store `python` is a stub). Commands write `python` for brevity — substitute the full path.
- **Core spine + all tests run key-free** with `StubJudge` and **no `ANTHROPIC_API_KEY`**. Only Task 17 (`ClaudeJudge`) needs the key.
- **Published numbers come from `ClaudeJudge` (Task 17), never `StubJudge`.** The stub is a CI smoke test and naive baseline, not a result.
- **Ground truth is generator-only.** `injected_labels` is the sole source of truth; detectors never read it (only `eval/*` and `generator/*` may).
- **Redact once, at the parser boundary.** The pipeline redacts each trace before detection; detectors assume an already-redacted trace and ground evidence spans against that same redacted trace.
- **Report counts alongside rates.** Every metric prints `tp/fp/fn/tn` next to `precision/recall/F1`; flag any cell with n < 200 as low-confidence.
- **Failure modes (canonical):** `phantom_action`, `error_masking`, `ungrounded`, `misrouting`, `clarification_loop`. Clean traces have `injected_labels == []`.
- **Severity map (fixed):** `phantom_action=5`, `error_masking=4`, `misrouting=4`, `ungrounded=3`, `clarification_loop=1`.
- **Confirm-words are one shared constant** (`CONFIRM_WORDS` in `generator/tools.py`); the judge, guardrail measurement, and heuristics-only baseline all import it.
- **Cost is a configurable overlay.** Default ranking is `freq × severity`; a customer cost weight defaults to 1.0. Never invent a dollar figure.
- **Two verticals in v1.** The generator emits fintech (`dispute_charge`) *and* subscription (`cancel_subscription`) phantom slices, so generality is demonstrated, not just claimed.
- **TDD, DRY, YAGNI, frequent commits.** Each task: failing test → run (fail) → minimal code → run (pass) → commit.

---

## File structure

```
parser/schema.py        Trace/Turn/ToolCall dataclasses (+timestamp, deploy_id, is_hard_negative); validate()
parser/redact.py        PII redaction to placeholders (parser-boundary; impr 5)
generator/tools.py      intent→tool surface, taxonomy, SEVERITY, CONFIRM_WORDS
generator/phrasings.py  per-intent phantom claims + ungrounded/clarify banks; frozen held-out partition (impr 4)
generator/generate.py   imbalanced dataset: clean, hard negatives (flagged), phantom (2 verticals), ungrounded
features/heuristics.py   cheap high-precision signals (features, not verdicts)
detector/judge.py       Judge protocol; Verdict(+model/prompt/usage); StubJudge; ClaudeJudge
detector/calibrate.py   reliability_bins + select_threshold + threshold_for (impr 1)
detector/detect.py      Detector protocol + DETECTORS registry; Phantom/Ungrounded/Routing; grounding (impr 2)
routing/routing.py      routing_mismatch heuristic + intent→action confusion
cluster/groupby.py      structured-signature group-by keyed by a stable signature_id (no ML)
reports/rank.py         freq × severity (+ optional cost overlay) ranking (impr 3)
reports/render.py       markdown report: signature, 3 examples, root cause, guardrail, annotated trace
guardrails/specs.py     guardrail spec per failure mode
guardrails/phantom.py   one implemented guardrail (structural trigger) + non-tautological before/after
eval/metrics.py         confusion counts + P/R/F1 + cohen_kappa (counts-first)
eval/harness.py         unified eval_mode, ablation, transfer loader
eval/regression.py      frozen regression-set runner
eval/published.py       Task 17: full harness under ClaudeJudge → published numbers + reliability diagram + κ
fixtures/transfer.jsonl ~15 hand-written transfer traces (impr 4)
run_v1.py               end-to-end CLI: generate → redact → detect (registry) → group → rank → report (StubJudge)
tests/                  one test module per source module
data/.gitkeep           generated datasets land here (gitignored)
```

---

### Task 1: Trace schema + validators

**Files:**
- Create: `parser/schema.py`, `parser/__init__.py` (empty)
- Test: `tests/test_schema.py`
- Modify: `pyproject.toml` (add `[calibrate]` extra; drop `hdbscan`/`numpy`)

**Interfaces:**
- Produces: `ToolCall`, `Turn`, `Trace` dataclasses; `Trace.from_dict(d)`; `Trace.to_dict()`; `validate(trace) -> list[str]`. `Trace` carries `timestamp: Optional[str] = None`, `deploy_id: Optional[str] = None`, `is_hard_negative: bool = False` (reserved for v2 streaming/dedup and for eval to flag hard negatives without id-string parsing).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schema.py
from parser.schema import Trace, validate

RAW = {
    "conversation_id": "c_001", "intent_true": "dispute_charge", "intent_routed": "dispute_charge",
    "injected_labels": ["phantom_action"],
    "turns": [
        {"role": "user", "text": "dispute a $50 charge", "tool_calls": []},
        {"role": "agent", "text": "Your dispute has been filed.",
         "tool_calls": [{"name": "file_dispute", "args": {"txn_id": "txn_8842"},
                          "result": {"success": False, "error": "txn_not_found"},
                          "status": "ok", "latency_ms": 220, "retrieved": None}]},
    ],
    "behavioral_signals": {"user_reask": False, "user_correction": False, "abandoned": False},
    "resolved": True, "csat": None, "timestamp": None, "deploy_id": None, "is_hard_negative": False,
}

def test_roundtrip_preserves_fields():
    t = Trace.from_dict(RAW)
    assert t.intent_true == "dispute_charge"
    assert t.turns[1].tool_calls[0].result["success"] is False
    assert t.to_dict() == RAW

def test_missing_optionals_default_and_validate_clean():
    minimal = {k: v for k, v in RAW.items() if k not in ("timestamp", "deploy_id", "is_hard_negative")}
    t = Trace.from_dict(minimal)
    assert t.timestamp is None and t.is_hard_negative is False
    assert validate(t) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser.schema'`

- [ ] **Step 3: Write minimal implementation**

```python
# parser/schema.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

VALID_LABELS = {"phantom_action", "error_masking", "ungrounded", "misrouting", "clarification_loop"}

@dataclass
class ToolCall:
    name: str
    args: dict
    result: dict
    status: str
    latency_ms: int
    retrieved: Optional[list[dict]] = None

    @staticmethod
    def from_dict(d: dict) -> "ToolCall":
        return ToolCall(d["name"], d["args"], d["result"], d["status"], d["latency_ms"], d.get("retrieved"))

    def to_dict(self) -> dict:
        return {"name": self.name, "args": self.args, "result": self.result,
                "status": self.status, "latency_ms": self.latency_ms, "retrieved": self.retrieved}

@dataclass
class Turn:
    role: str
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "Turn":
        return Turn(d["role"], d["text"], [ToolCall.from_dict(c) for c in d.get("tool_calls", [])])

    def to_dict(self) -> dict:
        return {"role": self.role, "text": self.text, "tool_calls": [c.to_dict() for c in self.tool_calls]}

@dataclass
class Trace:
    conversation_id: str
    intent_true: str
    intent_routed: str
    injected_labels: list[str]
    turns: list[Turn]
    behavioral_signals: dict
    resolved: bool
    csat: Optional[float]
    timestamp: Optional[str] = None
    deploy_id: Optional[str] = None
    is_hard_negative: bool = False

    @staticmethod
    def from_dict(d: dict) -> "Trace":
        return Trace(d["conversation_id"], d["intent_true"], d["intent_routed"], list(d["injected_labels"]),
                     [Turn.from_dict(t) for t in d["turns"]], d["behavioral_signals"], d["resolved"],
                     d.get("csat"), d.get("timestamp"), d.get("deploy_id"), d.get("is_hard_negative", False))

    def to_dict(self) -> dict:
        return {"conversation_id": self.conversation_id, "intent_true": self.intent_true,
                "intent_routed": self.intent_routed, "injected_labels": self.injected_labels,
                "turns": [t.to_dict() for t in self.turns], "behavioral_signals": self.behavioral_signals,
                "resolved": self.resolved, "csat": self.csat, "timestamp": self.timestamp,
                "deploy_id": self.deploy_id, "is_hard_negative": self.is_hard_negative}

def validate(trace: Trace) -> list[str]:
    errors: list[str] = []
    if not trace.conversation_id:
        errors.append("missing conversation_id")
    for lbl in trace.injected_labels:
        if lbl not in VALID_LABELS:
            errors.append(f"unknown label: {lbl}")
    if trace.turns and trace.turns[0].role != "user":
        errors.append("first turn must be user")
    return errors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_schema.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Update pyproject extras**

```toml
[project.optional-dependencies]
judge = ["anthropic>=0.39"]
calibrate = ["scikit-learn>=1.4"]
dev = ["pytest>=8.0"]
all = ["anthropic>=0.39", "scikit-learn>=1.4", "pytest>=8.0"]
```

- [ ] **Step 6: Commit**

```bash
git add parser/schema.py parser/__init__.py tests/test_schema.py pyproject.toml
git commit -m "feat(parser): trace schema (+v2-ready fields), validators, pyproject extras"
```

---

### Task 2: PII redaction at the parser boundary (impr 5)

**Files:**
- Create: `parser/redact.py`
- Test: `tests/test_redact.py`

**Interfaces:**
- Consumes: `Trace` (Task 1).
- Produces: `redact(trace) -> Trace` — a copy with PII arg values and id-shaped text mentions replaced by placeholders; `result.success`/`status`/keys preserved. Applied **once** by the pipeline before detection (never inside detectors).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_redact.py
from parser.schema import Trace
from parser.redact import redact
from tests.test_schema import RAW

def test_redacts_args_and_text_but_keeps_structure():
    r = redact(Trace.from_dict(RAW))
    tc = r.turns[1].tool_calls[0]
    assert tc.args["txn_id"] == "<txn_id>"
    assert tc.result["success"] is False and tc.result["error"] == "txn_not_found"
    assert "txn_8842" not in (r.turns[0].text + r.turns[1].text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_redact.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# parser/redact.py
from __future__ import annotations
import copy, re
from parser.schema import Trace

_PII_ARG_KEYS = {"txn_id", "account_id", "card_id", "name", "address"}
_ID_RE = re.compile(r"\b(txn|acct|account|card)_[A-Za-z0-9]+\b", re.IGNORECASE)

def _placeholder_for(key: str) -> str:
    return f"<{'txn_id' if key.startswith('txn') else key}>"

def _redact_text(text: str) -> str:
    return _ID_RE.sub(lambda m: f"<{m.group(1).lower().replace('acct', 'account')}_id>", text)

def redact(trace: Trace) -> Trace:
    t = copy.deepcopy(trace)
    for turn in t.turns:
        turn.text = _redact_text(turn.text)
        for call in turn.tool_calls:
            for k in list(call.args):
                if k in _PII_ARG_KEYS:
                    call.args[k] = _placeholder_for(k)
    return t
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_redact.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add parser/redact.py tests/test_redact.py
git commit -m "feat(parser): PII redaction at the parser boundary (impr 5)"
```

---

### Task 3: Tool surface, taxonomy, severity, confirm-words

**Files:**
- Create: `generator/tools.py`, `generator/__init__.py` (empty)
- Test: `tests/test_tools.py`

**Interfaces:**
- Produces: `INTENTS` (intent→`{tool, args, modes}`), `SEVERITY` (mode→int), `FAILURE_MODES`, `correct_tool(intent)`, and `CONFIRM_WORDS` (the single shared success-claim vocabulary).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools.py
from generator.tools import INTENTS, SEVERITY, correct_tool, CONFIRM_WORDS

def test_surface_and_severity():
    assert correct_tool("dispute_charge") == "file_dispute"
    assert correct_tool("cancel_subscription") == "cancel_subscription"
    assert SEVERITY["phantom_action"] == 5 > SEVERITY["ungrounded"]

def test_confirm_words_cover_dev_and_heldout_phantom_language():
    for w in ("filed", "submitted", "under dispute", "canceled"):
        assert w in CONFIRM_WORDS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tools.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# generator/tools.py
SEVERITY = {"phantom_action": 5, "error_masking": 4, "misrouting": 4, "ungrounded": 3, "clarification_loop": 1}
FAILURE_MODES = list(SEVERITY.keys())

# One shared success-claim vocabulary: judge stub, guardrail measurement, heuristics-only baseline.
CONFIRM_WORDS = ("filed", "on file", "submitted", "under dispute", "dispute is in",
                 "processed", "done", "canceled", "cancelled", "complete", "credited")

INTENTS = {
    "dispute_charge":      {"tool": "file_dispute",         "args": ["txn_id", "reason"], "modes": ["phantom_action", "misrouting"]},
    "request_refund":      {"tool": "issue_refund",         "args": ["txn_id", "amount"], "modes": ["error_masking"]},
    "check_balance":       {"tool": "get_balance",          "args": ["account_id"],       "modes": ["ungrounded"]},
    "cancel_subscription": {"tool": "cancel_subscription",  "args": ["account_id"],       "modes": ["phantom_action"]},
    "policy_question":     {"tool": "policy_search",        "args": ["query"],            "modes": ["ungrounded"]},
}

def correct_tool(intent: str) -> str:
    return INTENTS[intent]["tool"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tools.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add generator/tools.py generator/__init__.py tests/test_tools.py
git commit -m "feat(generator): tool surface, taxonomy, severity, shared CONFIRM_WORDS"
```

---

### Task 4: Phrasing banks with a frozen held-out partition (impr 4)

**Files:**
- Create: `generator/phrasings.py`
- Test: `tests/test_phrasings.py`

**Interfaces:**
- Produces: `phantom_claims(intent, held_out) -> list[str]` (intent-specific: dispute vs cancellation wording); `phrasings_for(mode, held_out) -> list[str]` (ungrounded/clarify); `USER_PHRASINGS[intent]`. Dev and held-out sets are disjoint. **Circularity note:** these banks stand in for "phrasing generated by a different process than the judge"; the held-out partition is frozen and used only at final eval.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_phrasings.py
from generator.phrasings import phantom_claims, phrasings_for

def test_dev_heldout_disjoint_per_intent():
    for intent in ("dispute_charge", "cancel_subscription"):
        dev, held = set(phantom_claims(intent, False)), set(phantom_claims(intent, True))
        assert dev and held and dev.isdisjoint(held)
    assert set(phrasings_for("ungrounded", False)).isdisjoint(set(phrasings_for("ungrounded", True)))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_phrasings.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# generator/phrasings.py
_PHANTOM = {
    "dispute_charge": {
        "dev":  ["Your dispute has been filed.", "All set — the dispute is in.", "I've filed that dispute for you."],
        "held": ["Great news, the dispute is officially submitted.", "That charge is now under dispute."]},
    "cancel_subscription": {
        "dev":  ["Your subscription is canceled.", "Done — your plan is canceled."],
        "held": ["All set, that subscription is complete and canceled.", "Your plan cancellation is submitted."]},
}
_MODE = {
    "ungrounded": {"dev": ["Our dispute window is 60 days.", "You have 60 days to dispute."],
                   "held": ["Disputes must be raised within 60 days.", "The policy gives you 60 days."]},
    "clarification_loop": {"dev": ["Sorry, could you clarify?"], "held": ["Could you rephrase that?"]},
}
USER_PHRASINGS = {
    "dispute_charge": ["I want to dispute a $50 charge", "there's a charge I didn't make"],
    "request_refund": ["I need a refund on my last order", "please refund me"],
    "check_balance": ["what's my balance?", "how much do I have?"],
    "cancel_subscription": ["cancel my subscription", "I want to cancel my plan"],
    "policy_question": ["how long do I have to dispute?", "what's the dispute window?"],
}

def phantom_claims(intent: str, held_out: bool) -> list[str]:
    return list(_PHANTOM[intent]["held" if held_out else "dev"])

def phrasings_for(mode: str, held_out: bool) -> list[str]:
    return list(_MODE.get(mode, {}).get("held" if held_out else "dev", []))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_phrasings.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add generator/phrasings.py tests/test_phrasings.py
git commit -m "feat(generator): per-intent phantom + mode phrasing banks with held-out partition"
```

---

### Task 5: Dataset generator (two verticals + flagged hard negatives)

**Files:**
- Create: `generator/generate.py`
- Test: `tests/test_generate.py`

**Interfaces:**
- Consumes: Tasks 1, 3, 4.
- Produces: `generate_dataset(n=1000, clean_ratio=0.8, held_out=False, seed=0) -> list[Trace]`; `composition(traces) -> dict`. Failure slice cycles `phantom(dispute_charge)` → `phantom(cancel_subscription)` → `ungrounded(policy_question)` → `misrouting(dispute_charge→refund)` — so every v1 detector (phantom, ungrounded, routing) has synthetic positives and a measurable recall. Hard negatives set `is_hard_negative=True`. Uses `random.Random(seed)` (deterministic). Every trace passes `validate`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generate.py
from generator.generate import generate_dataset, composition
from parser.schema import validate

def test_valid_balanced_two_vertical():
    ds = generate_dataset(n=300, seed=1)
    assert all(validate(t) == [] for t in ds)
    comp = composition(ds)
    assert 0.75 <= comp["clean_fraction"] <= 0.85
    intents = {t.intent_true for t in ds if "phantom_action" in t.injected_labels}
    assert {"dispute_charge", "cancel_subscription"} <= intents  # generality is real
    assert any("misrouting" in t.injected_labels for t in ds)    # routing has synthetic positives

def test_hard_negatives_flagged_and_labeled_clean():
    ds = generate_dataset(n=300, seed=1)
    hard = [t for t in ds if t.is_hard_negative]
    assert hard
    assert all(t.injected_labels == [] for t in hard)          # look failure-ish, are fine
    assert all(t.turns[-1].tool_calls[0].result.get("success") is True for t in hard)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_generate.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# generator/generate.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_generate.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add generator/generate.py tests/test_generate.py
git commit -m "feat(generator): imbalanced dataset, two phantom verticals, flagged hard negatives"
```

---

### Task 6: Heuristic features

**Files:**
- Create: `features/heuristics.py`, `features/__init__.py` (empty)
- Test: `tests/test_heuristics.py`

**Interfaces:**
- Consumes: Task 1, `correct_tool` (Task 3).
- Produces: `extract(trace) -> dict` of booleans: `any_tool_failed`, `null_result`, `low_retrieval_score`, `over_latency`, `intent_tool_mismatch`. Features, **not** verdicts.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_heuristics.py
from parser.schema import Trace
from features.heuristics import extract
from tests.test_schema import RAW

def test_tool_failure_signal():
    f = extract(Trace.from_dict(RAW))
    assert f["any_tool_failed"] is True and f["intent_tool_mismatch"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_heuristics.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# features/heuristics.py
from __future__ import annotations
from parser.schema import Trace
from generator.tools import correct_tool

LATENCY_TIMEOUT_MS = 1000
RETRIEVAL_TAU = 0.5

def extract(trace: Trace) -> dict:
    calls = [c for turn in trace.turns for c in turn.tool_calls]
    return {
        "any_tool_failed": any(c.result.get("success") is False for c in calls),
        "null_result": any(c.result in (None, {}) for c in calls),
        "low_retrieval_score": any(
            c.retrieved is not None and (not c.retrieved or max(r["score"] for r in c.retrieved) < RETRIEVAL_TAU)
            for c in calls),
        "over_latency": any(c.latency_ms > LATENCY_TIMEOUT_MS for c in calls),
        "intent_tool_mismatch": any(c.name != correct_tool(trace.intent_true) for c in calls) if calls else False,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_heuristics.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add features/heuristics.py features/__init__.py tests/test_heuristics.py
git commit -m "feat(features): heuristic signal extractor"
```

---

### Task 7: Judge seam — protocol, Verdict (+provenance), StubJudge, ClaudeJudge

**Files:**
- Create: `detector/judge.py`, `detector/__init__.py` (empty)
- Test: `tests/test_judge.py`

**Interfaces:**
- Consumes: Task 1; `CONFIRM_WORDS` (Task 3).
- Produces: `Verdict{failure_mode: Optional[str], confidence: float, evidence_span: str, model_version: str = "stub", prompt_version: str = "v1", usage: Optional[dict] = None}`; `Judge` protocol `assess(question, trace) -> Verdict`; `StubJudge` (key-free); `ClaudeJudge(model, api_key)` (lazy `anthropic`, records model/prompt/usage). The `usage`/version fields exist so v2 cost accounting and model pinning hang off an existing field, not a schema change.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_judge.py
from parser.schema import Trace
from detector.judge import StubJudge, Verdict
from tests.test_schema import RAW

def test_stub_flags_phantom_and_grounds_span():
    v = StubJudge().assess("phantom?", Trace.from_dict(RAW))
    assert isinstance(v, Verdict) and v.failure_mode == "phantom_action"
    assert v.evidence_span in RAW["turns"][1]["text"]
    assert v.model_version == "stub" and 0.0 <= v.confidence <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_judge.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# detector/judge.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol
from parser.schema import Trace
from generator.tools import CONFIRM_WORDS

@dataclass
class Verdict:
    failure_mode: Optional[str]
    confidence: float
    evidence_span: str
    model_version: str = "stub"
    prompt_version: str = "v1"
    usage: Optional[dict] = None

class Judge(Protocol):
    def assess(self, question: str, trace: Trace) -> Verdict: ...

class StubJudge:
    """Deterministic, key-free naive baseline for CI. Phantom-only by design."""
    def assess(self, question: str, trace: Trace) -> Verdict:
        agents = [t for t in trace.turns if t.role == "agent"]
        if not agents:
            return Verdict(None, 0.0, "")
        last = agents[-1]
        failed = any(c.result.get("success") is False for c in last.tool_calls)
        hit = next((w for w in CONFIRM_WORDS if w in last.text.lower()), None)
        if failed and hit:
            idx = last.text.lower().index(hit)
            return Verdict("phantom_action", 0.9, last.text[idx:idx + len(hit)])
        return Verdict(None, 0.1, "")

class ClaudeJudge:
    """Real judge (temp 0). Lazy anthropic import keeps the core spine key-free."""
    def __init__(self, model: str = "claude-opus-4-8", api_key: Optional[str] = None, prompt_version: str = "v1"):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._pv = prompt_version

    def assess(self, question: str, trace: Trace) -> Verdict:
        import json
        prompt = (f"{question}\nReturn JSON {{failure_mode, confidence, evidence_span}}. "
                  f"evidence_span MUST be a verbatim substring of the conversation.\n"
                  f"CONVERSATION:\n{json.dumps(trace.to_dict())}")
        msg = self._client.messages.create(model=self._model, max_tokens=300, temperature=0,
                                           messages=[{"role": "user", "content": prompt}])
        data = json.loads(msg.content[0].text)
        usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
        return Verdict(data.get("failure_mode"), float(data.get("confidence", 0.0)),
                       data.get("evidence_span", ""), self._model, self._pv, usage)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_judge.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add detector/judge.py detector/__init__.py tests/test_judge.py
git commit -m "feat(detector): Judge protocol + Verdict provenance + Stub/Claude judges"
```

---

### Task 8: Calibration + per-severity thresholds (impr 1)

**Files:**
- Create: `detector/calibrate.py`
- Test: `tests/test_calibrate.py`

**Interfaces:**
- Consumes: `SEVERITY` (Task 3).
- Produces: `reliability_bins(confidences, correct, n_bins=10) -> list[dict]`; `select_threshold(confidences, correct, objective, floor) -> float`; `threshold_for(mode) -> float`. Built **before** the detector so detectors consume `threshold_for`. Interface is a drop-in seam for a future sklearn isotonic upgrade.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_calibrate.py
from detector.calibrate import select_threshold, threshold_for

def test_recall_objective_low_threshold():
    thr = select_threshold([0.2, 0.4, 0.6, 0.8, 0.95], [False, False, True, True, True],
                           objective="recall", floor=0.95)
    assert thr <= 0.6

def test_critical_is_recall_first():
    assert threshold_for("phantom_action") < threshold_for("clarification_loop")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_calibrate.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# detector/calibrate.py
from __future__ import annotations
from generator.tools import SEVERITY

def reliability_bins(confidences, correct, n_bins: int = 10) -> list[dict]:
    bins = []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        idx = [j for j, c in enumerate(confidences) if lo <= c < hi or (hi == 1.0 and c == 1.0)]
        if idx:
            bins.append({"lo": lo, "hi": hi, "n": len(idx),
                         "mean_conf": sum(confidences[j] for j in idx) / len(idx),
                         "accuracy": sum(1 for j in idx if correct[j]) / len(idx)})
        else:
            bins.append({"lo": lo, "hi": hi, "n": 0, "mean_conf": 0.0, "accuracy": 0.0})
    return bins

def select_threshold(confidences, correct, objective: str, floor: float) -> float:
    candidates = sorted(set(confidences))
    if not candidates:
        return 0.5
    for thr in (candidates if objective == "recall" else list(reversed(candidates))):
        pred = [c >= thr for c in confidences]
        tp = sum(1 for p, y in zip(pred, correct) if p and y)
        fp = sum(1 for p, y in zip(pred, correct) if p and not y)
        fn = sum(1 for p, y in zip(pred, correct) if not p and y)
        value = (tp / (tp + fn) if objective == "recall" and (tp + fn) else
                 tp / (tp + fp) if (tp + fp) else 0.0)
        if value >= floor:
            return thr
    return candidates[-1]

def threshold_for(mode: str) -> float:
    """Critical/High -> recall-first (low); Medium -> balanced; Low -> precision-first (high)."""
    sev = SEVERITY[mode]
    return 0.3 if sev >= 4 else 0.5 if sev == 3 else 0.8
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_calibrate.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add detector/calibrate.py tests/test_calibrate.py
git commit -m "feat(detector): calibration bins + per-severity thresholds (impr 1)"
```

---

### Task 9: Detector protocol + registry + PhantomDetector (impr 2)

**Files:**
- Create: `detector/detect.py`
- Test: `tests/test_detect.py`

**Interfaces:**
- Consumes: `extract` (Task 6); `Judge`/`Verdict` (Task 7); `threshold_for` (Task 8); `SEVERITY` (Task 3).
- Produces: `Detection{conversation_id, failure_mode, severity, confidence, evidence_span, heuristics_hit}`; `grounds(span, trace) -> bool`; `Detector` protocol (`mode: str`, `detect(trace, judge, threshold=None) -> Optional[Detection]`); `PhantomDetector`; the `DETECTORS: dict[str, Detector]` registry (phantom now; later tasks append). Detectors assume the trace is **already redacted** and ground the span against that same trace. When `threshold is None`, the detector uses `threshold_for(mode)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_detect.py
from parser.schema import Trace
from parser.redact import redact
from detector.detect import DETECTORS, grounds
from detector.judge import StubJudge, Verdict
from tests.test_schema import RAW

class _UngroundedJudge:
    def assess(self, q, t): return Verdict("phantom_action", 0.99, "NOT IN THE TRACE")

def test_phantom_detector_via_registry():
    tr = redact(Trace.from_dict(RAW))
    d = DETECTORS["phantom_action"].detect(tr, StubJudge())   # threshold=None -> threshold_for
    assert d is not None and d.failure_mode == "phantom_action" and d.severity == 5
    assert "any_tool_failed" in d.heuristics_hit

def test_rejects_ungrounded_verdict():
    tr = redact(Trace.from_dict(RAW))
    assert DETECTORS["phantom_action"].detect(tr, _UngroundedJudge()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_detect.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# detector/detect.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol
from parser.schema import Trace
from features.heuristics import extract
from detector.judge import Judge
from detector.calibrate import threshold_for
from generator.tools import SEVERITY

@dataclass
class Detection:
    conversation_id: str
    failure_mode: str
    severity: int
    confidence: float
    evidence_span: str
    heuristics_hit: list[str]

def grounds(span: str, trace: Trace) -> bool:
    if not span:
        return False
    hay = " ".join(t.text for t in trace.turns)
    hay += " " + " ".join(str(c.result) for turn in trace.turns for c in turn.tool_calls)
    return span in hay

class Detector(Protocol):
    mode: str
    def detect(self, trace: Trace, judge: Judge, threshold: Optional[float] = None) -> Optional[Detection]: ...

class _JudgeDetector:
    mode = ""
    question = ""
    def detect(self, trace: Trace, judge: Judge, threshold: Optional[float] = None) -> Optional[Detection]:
        thr = threshold if threshold is not None else threshold_for(self.mode)
        hits = [k for k, v in extract(trace).items() if v is True]
        v = judge.assess(self.question, trace)          # trace is already redacted by the caller
        if v.failure_mode != self.mode or v.confidence < thr:
            return None
        if not grounds(v.evidence_span, trace):          # impr 2: reject verdicts the judge can't point at
            return None
        return Detection(trace.conversation_id, self.mode, SEVERITY[self.mode],
                         v.confidence, v.evidence_span, hits)

class PhantomDetector(_JudgeDetector):
    mode = "phantom_action"
    question = "Does the response claim an outcome the tool results don't support?"

DETECTORS: dict[str, Detector] = {"phantom_action": PhantomDetector()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_detect.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add detector/detect.py tests/test_detect.py
git commit -m "feat(detector): Detector protocol + registry + PhantomDetector with grounding (impr 2)"
```

---

### Task 10: Metrics + unified eval (first honest number)

**Files:**
- Create: `eval/metrics.py`, `eval/harness.py`, `eval/__init__.py` (empty)
- Test: `tests/test_metrics.py`, `tests/test_harness.py`

**Interfaces:**
- Consumes: `generate_dataset` (Task 5); `redact` (Task 2); `DETECTORS` (Task 9); `StubJudge` (Task 7).
- Produces: `confusion(y_true, y_pred)`; `prf(counts)`; `cohen_kappa(y_true, y_pred)`; `eval_mode(mode, traces, judge, threshold=None) -> dict` (redacts each trace, runs `DETECTORS[mode]`, returns counts, rates, `kappa`, and `hard_negative_fp` counted via the `is_hard_negative` flag).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_metrics.py
from eval.metrics import confusion, prf, cohen_kappa

def test_confusion_prf_kappa():
    c = confusion([True, True, False, False], [True, False, False, False])
    assert c == {"tp": 1, "fp": 0, "fn": 1, "tn": 2}
    assert prf(c)["precision"] == 1.0 and prf(c)["recall"] == 0.5
    assert cohen_kappa([True, False], [True, False]) == 1.0
```

```python
# tests/test_harness.py
from generator.generate import generate_dataset
from detector.judge import StubJudge
from eval.harness import eval_mode

def test_phantom_eval_counts_and_hard_neg_fp():
    ds = generate_dataset(n=300, seed=2)
    res = eval_mode("phantom_action", ds, StubJudge())
    assert set(res["counts"]) == {"tp", "fp", "fn", "tn"}
    assert res["rates"]["recall"] > 0.8
    assert res["hard_negative_fp"] == 0        # hard negatives (tool succeeded) must not flag
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_metrics.py tests/test_harness.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# eval/metrics.py
def confusion(y_true, y_pred) -> dict:
    return {
        "tp": sum(1 for t, p in zip(y_true, y_pred) if t and p),
        "fp": sum(1 for t, p in zip(y_true, y_pred) if not t and p),
        "fn": sum(1 for t, p in zip(y_true, y_pred) if t and not p),
        "tn": sum(1 for t, p in zip(y_true, y_pred) if not t and not p),
    }

def prf(c: dict) -> dict:
    p = c["tp"] / (c["tp"] + c["fp"]) if (c["tp"] + c["fp"]) else 0.0
    r = c["tp"] / (c["tp"] + c["fn"]) if (c["tp"] + c["fn"]) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": p, "recall": r, "f1": f1}

def cohen_kappa(y_true, y_pred) -> float:
    c = confusion(y_true, y_pred)
    n = sum(c.values())
    if not n:
        return 0.0
    po = (c["tp"] + c["tn"]) / n
    pe = (((c["tp"] + c["fp"]) * (c["tp"] + c["fn"])) + ((c["fn"] + c["tn"]) * (c["fp"] + c["tn"]))) / (n * n)
    return (po - pe) / (1 - pe) if (1 - pe) else 0.0
```

```python
# eval/harness.py
from parser.redact import redact
from eval.metrics import confusion, prf, cohen_kappa
from detector.detect import DETECTORS

def eval_mode(mode: str, traces, judge, threshold=None) -> dict:
    det = DETECTORS[mode]
    y_true = [mode in t.injected_labels for t in traces]
    y_pred = [det.detect(redact(t), judge, threshold) is not None for t in traces]
    counts = confusion(y_true, y_pred)
    hard_neg_fp = sum(1 for t, p in zip(traces, y_pred) if p and t.is_hard_negative)
    return {"mode": mode, "counts": counts, "rates": prf(counts),
            "kappa": cohen_kappa(y_true, y_pred), "hard_negative_fp": hard_neg_fp, "n": len(traces)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_metrics.py tests/test_harness.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add eval/metrics.py eval/harness.py eval/__init__.py tests/test_metrics.py tests/test_harness.py
git commit -m "feat(eval): counts-first metrics (+kappa) and unified eval_mode with flag-based hard-neg FP"
```

---

### Task 11: UngroundedDetector (registry entry)

**Files:**
- Modify: `detector/detect.py` (add `UngroundedDetector`, register it)
- Test: `tests/test_ungrounded.py`

**Interfaces:**
- Produces: `UngroundedDetector` registered as `DETECTORS["ungrounded"]`; reuses `_JudgeDetector` (grounding + threshold identical to phantom). No new eval code — `eval_mode("ungrounded", …)` already works via the registry.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ungrounded.py
from parser.schema import Trace, Turn, ToolCall
from parser.redact import redact
from detector.detect import DETECTORS
from detector.judge import Verdict

class _UngroundedJudge:
    def assess(self, q, t): return Verdict("ungrounded", 0.9, "60 days")

def _policy():
    call = ToolCall("policy_search", {"query": "dispute window"}, {"success": True}, "ok", 120,
                    retrieved=[{"chunk_id": "k1", "text": "window is 90 days", "score": 0.2}])
    return Trace("u_1", "policy_question", "policy_question", ["ungrounded"],
                 [Turn("user", "how long to dispute?"), Turn("agent", "Our dispute window is 60 days.", [call])],
                 {"user_reask": False, "user_correction": False, "abandoned": False}, True, None)

def test_ungrounded_via_registry():
    d = DETECTORS["ungrounded"].detect(redact(_policy()), _UngroundedJudge())
    assert d is not None and d.failure_mode == "ungrounded" and d.severity == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ungrounded.py -v`
Expected: FAIL with `KeyError: 'ungrounded'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to detector/detect.py (after PhantomDetector)
class UngroundedDetector(_JudgeDetector):
    mode = "ungrounded"
    question = "Is every factual claim grounded in a retrieved chunk above threshold?"

DETECTORS["ungrounded"] = UngroundedDetector()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ungrounded.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add detector/detect.py tests/test_ungrounded.py
git commit -m "feat(detector): ungrounded detector as a registry entry"
```

---

### Task 12: RoutingDetector + intent→action confusion

**Files:**
- Create: `routing/routing.py`, `routing/__init__.py` (empty)
- Modify: `detector/detect.py` (register `RoutingDetector`)
- Test: `tests/test_routing.py`

**Interfaces:**
- Consumes: Task 1; `correct_tool` (Task 3); `Detection` (Task 9).
- Produces: `routing_mismatch(trace) -> bool` (heuristic; `user_correction` traces never flag); `intent_action_confusion(traces) -> dict` (true intent vs routed action counts); `RoutingDetector` registered as `DETECTORS["misrouting"]` (judge-free; evidence span = the final agent text, which grounds).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_routing.py
from parser.schema import Trace, Turn, ToolCall
from parser.redact import redact
from routing.routing import routing_mismatch
from detector.detect import DETECTORS

def _misrouted():
    call = ToolCall("issue_refund", {"txn_id": "t"}, {"success": True}, "ok", 100, None)
    return Trace("m_1", "dispute_charge", "request_refund", ["misrouting"],
                 [Turn("user", "dispute this charge"), Turn("agent", "Refund processed.", [call])],
                 {"user_reask": False, "user_correction": False, "abandoned": False}, True, None)

def test_flags_intent_action_mismatch():
    assert routing_mismatch(_misrouted()) is True

def test_routing_detector_registered():
    d = DETECTORS["misrouting"].detect(redact(_misrouted()), judge=None)
    assert d is not None and d.failure_mode == "misrouting"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_routing.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# routing/routing.py
from __future__ import annotations
from parser.schema import Trace
from generator.tools import correct_tool

def routing_mismatch(trace: Trace) -> bool:
    if trace.behavioral_signals.get("user_correction"):
        return False
    if trace.intent_routed != trace.intent_true:
        return True
    calls = [c for turn in trace.turns for c in turn.tool_calls]
    return any(c.name != correct_tool(trace.intent_true) for c in calls)

def intent_action_confusion(traces) -> dict:
    table: dict[tuple, int] = {}
    for t in traces:
        served = correct_tool(t.intent_routed) if t.intent_routed in ("dispute_charge", "request_refund",
                 "check_balance", "cancel_subscription", "policy_question") else t.intent_routed
        key = (t.intent_true, served)
        table[key] = table.get(key, 0) + 1
    return table
```

```python
# add to detector/detect.py (after UngroundedDetector)
from routing.routing import routing_mismatch

class RoutingDetector:
    mode = "misrouting"
    def detect(self, trace, judge=None, threshold=None):
        if not routing_mismatch(trace):
            return None
        agents = [t for t in trace.turns if t.role == "agent"]
        span = agents[-1].text if agents else ""
        return Detection(trace.conversation_id, self.mode, SEVERITY[self.mode], 1.0, span,
                         ["intent_tool_mismatch"])

DETECTORS["misrouting"] = RoutingDetector()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_routing.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add routing/routing.py routing/__init__.py detector/detect.py tests/test_routing.py
git commit -m "feat(routing): routing-mismatch detector + intent→action confusion"
```

---

### Task 13: Ablation + hand-written transfer set (impr 4)

**Files:**
- Create: `fixtures/transfer.jsonl` (~15 hand-written traces)
- Modify: `eval/harness.py` (add `load_transfer`, `ablation`)
- Test: `tests/test_transfer.py`

**Interfaces:**
- Consumes: `DETECTORS` (Task 9); `extract` (Task 6); `CONFIRM_WORDS` (Task 3).
- Produces: `load_transfer(path="fixtures/transfer.jsonl") -> list[Trace]`; `ablation(traces, judge) -> dict` with `heuristics_only` (predict phantom iff `any_tool_failed` and a `CONFIRM_WORDS` hit, no judge) and `hybrid` (the registry detector), each counts + rates.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_transfer.py
from eval.harness import load_transfer, ablation
from detector.judge import StubJudge

def test_transfer_loads_labeled():
    ts = load_transfer()
    assert len(ts) >= 12 and all(isinstance(t.injected_labels, list) for t in ts)

def test_ablation_two_rows():
    ab = ablation(load_transfer(), StubJudge())
    assert set(ab) == {"heuristics_only", "hybrid"} and "rates" in ab["hybrid"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transfer.py -v`
Expected: FAIL with `ModuleNotFoundError` / `FileNotFoundError`

- [ ] **Step 3: Author fixtures and implementation**

Author `fixtures/transfer.jsonl` **by hand** — 15 one-line JSON traces (Task 1 schema, all keys including `timestamp:null, deploy_id:null, is_hard_negative:false`), NOT copied from generator templates: mix phantom (dispute + cancel), ungrounded, misrouting, hard negatives, clean, with hand-written wording. Example line:

```json
{"conversation_id": "t_01", "intent_true": "dispute_charge", "intent_routed": "dispute_charge", "injected_labels": ["phantom_action"], "turns": [{"role": "user", "text": "someone used my card, I want to dispute it", "tool_calls": []}, {"role": "agent", "text": "No problem, that dispute is on file now.", "tool_calls": [{"name": "file_dispute", "args": {"txn_id": "txn_x"}, "result": {"success": false, "error": "downstream_5xx"}, "status": "ok", "latency_ms": 300, "retrieved": null}]}], "behavioral_signals": {"user_reask": false, "user_correction": false, "abandoned": false}, "resolved": true, "csat": null, "timestamp": null, "deploy_id": null, "is_hard_negative": false}
```

```python
# add to eval/harness.py
import json
from parser.schema import Trace
from features.heuristics import extract
from generator.tools import CONFIRM_WORDS

def load_transfer(path: str = "fixtures/transfer.jsonl") -> list[Trace]:
    with open(path, encoding="utf-8") as fh:
        return [Trace.from_dict(json.loads(line)) for line in fh if line.strip()]

def _heuristics_only_pred(trace) -> bool:
    agents = [t for t in trace.turns if t.role == "agent"]
    confident = bool(agents) and any(w in agents[-1].text.lower() for w in CONFIRM_WORDS)
    return extract(trace)["any_tool_failed"] and confident

def ablation(traces, judge) -> dict:
    y_true = ["phantom_action" in t.injected_labels for t in traces]
    heur = [_heuristics_only_pred(t) for t in traces]
    hybrid = [DETECTORS["phantom_action"].detect(redact(t), judge) is not None for t in traces]
    return {"heuristics_only": {"counts": confusion(y_true, heur), "rates": prf(confusion(y_true, heur))},
            "hybrid": {"counts": confusion(y_true, hybrid), "rates": prf(confusion(y_true, hybrid))}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transfer.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add fixtures/transfer.jsonl eval/harness.py tests/test_transfer.py
git commit -m "feat(eval): ablation + hand-written transfer set (impr 4)"
```

---

### Task 14: One guardrail, end-to-end + non-tautological before/after

**Files:**
- Create: `guardrails/specs.py`, `guardrails/phantom.py`, `guardrails/__init__.py` (empty)
- Test: `tests/test_guardrail.py`

**Interfaces:**
- Consumes: Task 1; `generate_dataset` (Task 5); `CONFIRM_WORDS` (Task 3).
- Produces: `GUARDRAILS` (mode→rule); `apply_phantom_guardrail(trace) -> Trace` — **structural trigger**: if the final agent turn has a `file_dispute` call whose result lacks a `dispute_id`, rewrite the text to a handoff; `before_after(n=300, seed=3) -> dict`. **Non-tautological:** the guardrail triggers on tool *structure*; the metric measures success-*claim text* (`CONFIRM_WORDS`) on the ground-truth dispute-phantom slice — so a phantom the guardrail misses would still show as a claim.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guardrail.py
from parser.schema import Trace
from guardrails.phantom import apply_phantom_guardrail, before_after
from tests.test_schema import RAW

def test_rewrites_structural_phantom_to_handoff():
    fixed = apply_phantom_guardrail(Trace.from_dict(RAW))   # file_dispute, no dispute_id
    assert "filed" not in fixed.turns[-1].text.lower() and "connect you" in fixed.turns[-1].text.lower()

def test_before_after_reduces_dispute_phantom_claims():
    ba = before_after(n=300, seed=3)
    assert ba["phantom_confirmation_rate_off"] > ba["phantom_confirmation_rate_on"]
    assert ba["phantom_confirmation_rate_on"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_guardrail.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# guardrails/specs.py
GUARDRAILS = {
    "phantom_action": "Don't confirm a dispute unless file_dispute returns a dispute_id.",
    "error_masking": "Don't claim 'processed' on any non-2xx tool result; surface a handoff.",
    "ungrounded": "Don't state a policy figure without a retrieved chunk above score tau; cite it.",
    "misrouting": "Re-confirm intent before any state-changing tool call when routing confidence < tau.",
}
```

```python
# guardrails/phantom.py
from __future__ import annotations
import copy
from parser.schema import Trace
from generator.generate import generate_dataset
from generator.tools import CONFIRM_WORDS

_HANDOFF = "I wasn't able to finish that — let me connect you with a specialist."  # no CONFIRM_WORD substring

def _last_agent(trace: Trace):
    agents = [t for t in trace.turns if t.role == "agent"]
    return agents[-1] if agents else None

def apply_phantom_guardrail(trace: Trace) -> Trace:
    t = copy.deepcopy(trace)
    last = _last_agent(t)
    if not last:
        return t
    dispute_calls = [c for c in last.tool_calls if c.name == "file_dispute"]
    if dispute_calls and any("dispute_id" not in c.result for c in dispute_calls):   # structural trigger
        last.text = _HANDOFF
    return t

def _still_claims_success(trace: Trace) -> bool:
    last = _last_agent(trace)
    return bool(last) and any(w in last.text.lower() for w in CONFIRM_WORDS)

def before_after(n: int = 300, seed: int = 3) -> dict:
    ds = generate_dataset(n=n, seed=seed)
    slice_ = [t for t in ds if "phantom_action" in t.injected_labels and t.intent_true == "dispute_charge"]
    off = sum(_still_claims_success(t) for t in slice_) / max(1, len(slice_))
    on_traces = [apply_phantom_guardrail(t) for t in slice_]
    on = sum(_still_claims_success(t) for t in on_traces) / max(1, len(slice_))
    handed = sum("connect you" in _last_agent(t).text.lower() for t in on_traces) / max(1, len(slice_))
    return {"phantom_confirmation_rate_off": off, "phantom_confirmation_rate_on": on,
            "handed_off_rate": handed, "slice_n": len(slice_)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_guardrail.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add guardrails/ tests/test_guardrail.py
git commit -m "feat(guardrails): structural phantom guardrail + non-tautological before/after"
```

---

### Task 15: Group-by (stable signature) + ranked report + cost overlay (impr 3)

**Files:**
- Create: `cluster/groupby.py`, `cluster/__init__.py` (empty); `reports/rank.py`, `reports/render.py`, `reports/__init__.py` (empty)
- Test: `tests/test_groupby.py`, `tests/test_rank.py`

**Interfaces:**
- Consumes: `Detection` (Task 9); `SEVERITY` (Task 3); `GUARDRAILS` (Task 14).
- Produces: `signature(detection, trace) -> tuple` (tool taken from the **actual** `ToolCall`, not `correct_tool` — so misrouting isn't hidden); `signature_id(sig) -> str` (stable hash of the structural fields only, dropping the volatile claim snippet); `group(pairs) -> dict[str, dict]` keyed by `signature_id`; `rank(groups, cost_weights=None) -> list[dict]` scored `freq × severity × cost_weight` (default 1.0); `render_markdown(ranked, groups) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_groupby.py
from cluster.groupby import group
from detector.detect import Detection
from parser.schema import Trace
from tests.test_schema import RAW

def test_same_signature_groups_and_uses_actual_tool():
    tr = Trace.from_dict(RAW)
    d = Detection("c_001", "phantom_action", 5, 0.9, "filed", ["any_tool_failed"])
    g = group([(d, tr), (d, tr)])
    assert len(g) == 1
    only = next(iter(g.values()))
    assert only["signature"][2] == "file_dispute"   # actual tool from the ToolCall
    assert len(only["members"]) == 2
```

```python
# tests/test_rank.py
from reports.rank import rank

def test_cost_overlay_default_and_weighted():
    groups = {"a": {"signature": ("phantom_action", "dispute_charge", "file_dispute", "txn_not_found", "filed"),
                    "members": [1, 2]},
              "b": {"signature": ("ungrounded", "policy_question", "policy_search", "low_score", "60 days"),
                    "members": [1, 2, 3, 4]}}
    default = rank(groups)
    assert default[0]["signature"][0] == "ungrounded"          # 4×3=12 > 2×5=10
    weighted = rank(groups, cost_weights={"phantom_action": 3.0})
    assert weighted[0]["signature"][0] == "phantom_action"     # 2×5×3=30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_groupby.py tests/test_rank.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# cluster/groupby.py
from __future__ import annotations
import hashlib

def _relevant_call(trace):
    for turn in reversed(trace.turns):
        if turn.tool_calls:
            return turn.tool_calls[-1]
    return None

def _error_type(call) -> str:
    if call is None:
        return "none"
    if call.result.get("success") is False:
        return call.result.get("error", "unknown")
    if call.retrieved is not None:
        return "low_score"
    return "none"

def signature(detection, trace) -> tuple:
    call = _relevant_call(trace)
    tool = call.name if call else "none"                     # actual tool taken, not correct_tool
    return (detection.failure_mode, trace.intent_true, tool, _error_type(call), detection.evidence_span[:40])

def signature_id(sig: tuple) -> str:
    key = "|".join(str(x) for x in sig[:4])                  # structural only; drop volatile claim snippet
    return hashlib.sha1(key.encode()).hexdigest()[:12]

def group(pairs) -> dict:
    out: dict[str, dict] = {}
    for det, tr in pairs:
        sig = signature(det, tr)
        sid = signature_id(sig)
        out.setdefault(sid, {"signature": sig, "members": []})["members"].append((det, tr))
    return out
```

```python
# reports/rank.py
from __future__ import annotations
from generator.tools import SEVERITY

def rank(groups, cost_weights=None) -> list[dict]:
    cost_weights = cost_weights or {}
    rows = []
    for sid, g in groups.items():
        mode = g["signature"][0]
        freq = len(g["members"])
        weight = cost_weights.get(mode, 1.0)
        rows.append({"signature_id": sid, "signature": g["signature"], "freq": freq,
                     "severity": SEVERITY[mode], "cost_weight": weight,
                     "score": freq * SEVERITY[mode] * weight})
    return sorted(rows, key=lambda r: r["score"], reverse=True)
```

```python
# reports/render.py
from __future__ import annotations
from guardrails.specs import GUARDRAILS

def render_markdown(ranked, groups) -> str:
    lines = ["# Silent-Failure Report", ""]
    for i, row in enumerate(ranked, 1):
        sig = row["signature"]
        lines += [f"## #{i} — {sig[0]} ({sig[1]} → {sig[2]})",
                  f"- **Frequency:** {row['freq']}  **Severity:** {row['severity']}  **Score:** {row['score']}",
                  f"- **Root-cause hypothesis:** tool `{sig[2]}` returned `{sig[3]}` while the agent claimed success.",
                  f"- **Guardrail to ship:** {GUARDRAILS.get(sig[0], 'n/a')}",
                  "- **Examples:**"]
        for det, tr in groups[row["signature_id"]]["members"][:3]:
            lines.append(f"  - `{tr.conversation_id}`: “…{det.evidence_span}…”")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_groupby.py tests/test_rank.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add cluster/ reports/ tests/test_groupby.py tests/test_rank.py
git commit -m "feat(reports): stable-id group-by (actual tool) + freq×severity ranking with cost overlay (impr 3)"
```

---

### Task 16: Regression set + end-to-end CLI (StubJudge)

**Files:**
- Create: `eval/regression.py`, `run_v1.py`
- Test: `tests/test_regression.py`, `tests/test_end_to_end.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `check_regression(judge) -> dict` (phantom recall ≥ frozen floor on the transfer set); `run_v1.py` `main(n, seed, out_dir, judge=None)` — redacts once, loops **all** `DETECTORS`, groups, ranks, writes `reports/out/report.md`, and prints the phantom + ungrounded + routing eval blocks plus the intent→action confusion.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_regression.py
from eval.regression import check_regression
from detector.judge import StubJudge

def test_regression_floor_holds():
    res = check_regression(StubJudge())
    assert res["phantom_recall"] >= res["floor"]
```

```python
# tests/test_end_to_end.py
import os
from run_v1 import main

def test_end_to_end_writes_report(tmp_path):
    out = main(n=300, seed=5, out_dir=str(tmp_path))
    assert os.path.exists(out["report_path"])
    assert out["eval"]["phantom_action"]["rates"]["recall"] > 0.8
    assert "misrouting" in out["eval"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_regression.py tests/test_end_to_end.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# eval/regression.py
from eval.harness import load_transfer, eval_mode

PHANTOM_RECALL_FLOOR = 0.8

def check_regression(judge) -> dict:
    res = eval_mode("phantom_action", load_transfer(), judge)
    return {"phantom_recall": res["rates"]["recall"], "floor": PHANTOM_RECALL_FLOOR, "counts": res["counts"]}
```

```python
# run_v1.py
from __future__ import annotations
import os
from generator.generate import generate_dataset
from parser.redact import redact
from detector.judge import StubJudge
from detector.detect import DETECTORS
from eval.harness import eval_mode
from routing.routing import intent_action_confusion
from cluster.groupby import group
from reports.rank import rank
from reports.render import render_markdown

def main(n: int = 1000, seed: int = 0, out_dir: str = "reports/out", judge=None) -> dict:
    judge = judge or StubJudge()
    ds = generate_dataset(n=n, seed=seed)
    pairs = []
    for t in ds:
        rt = redact(t)
        for det in DETECTORS.values():
            d = det.detect(rt, judge)
            if d:
                pairs.append((d, t))
                break
    groups = group(pairs)
    ranked = rank(groups)
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, "report.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(ranked, groups))
    evaluation = {m: eval_mode(m, ds, judge) for m in ("phantom_action", "ungrounded", "misrouting")}
    print("PHANTOM:", evaluation["phantom_action"]["counts"], evaluation["phantom_action"]["rates"])
    print("INTENT→ACTION:", intent_action_confusion(ds))
    return {"report_path": report_path, "eval": evaluation, "n_patterns": len(ranked)}

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests + suite + CLI**

Run: `python -m pytest -q` → Expected: all pass.
Run: `python run_v1.py` → Expected: prints PHANTOM + INTENT→ACTION and writes `reports/out/report.md`.

- [ ] **Step 5: Commit**

```bash
git add eval/regression.py run_v1.py tests/test_regression.py tests/test_end_to_end.py
git commit -m "feat: frozen regression set + end-to-end registry pipeline CLI"
```

---

### Task 17: Published numbers under ClaudeJudge (the gating task)

**Files:**
- Create: `eval/published.py`
- Test: `tests/test_published.py`

**Interfaces:**
- Consumes: `generate_dataset(held_out=True)`; `eval_mode`, `ablation`, `load_transfer` (Tasks 10/13); `reliability_bins` (Task 8); `cohen_kappa` (Task 10); `ClaudeJudge` (Task 7).
- Produces: `collect_conf_correct(mode, traces, judge) -> tuple[list, list]`; `run_published(n=1000, seed=7, out_dir="reports/out", judge=None) -> dict` — runs the full harness under the given judge (default `ClaudeJudge`, requires `ANTHROPIC_API_KEY`) on the **held-out** slice and writes `published.md` with: per-mode P/R/F1 + counts + κ, the hard-negative FP, the ablation table, the transfer-set result, and a reliability diagram. **This is the source of every number in the case study.** Guard: if no key, print a clear skip message and return `{"skipped": True}` so CI stays green.

- [ ] **Step 1: Write the failing test** (runs under a fake judge — no key needed in CI)

```python
# tests/test_published.py
from generator.generate import generate_dataset
from eval.published import run_published
from detector.judge import StubJudge

def test_run_published_shape_with_injected_judge(tmp_path):
    out = run_published(n=200, seed=7, out_dir=str(tmp_path), judge=StubJudge())
    assert not out.get("skipped")
    assert "phantom_action" in out["per_mode"]
    assert "reliability" in out and "ablation" in out
    assert set(out["per_mode"]["phantom_action"]["counts"]) == {"tp", "fp", "fn", "tn"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_published.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# eval/published.py
from __future__ import annotations
import os
from generator.generate import generate_dataset
from parser.redact import redact
from detector.detect import DETECTORS
from eval.harness import eval_mode, ablation, load_transfer
from eval.metrics import cohen_kappa
from detector.calibrate import reliability_bins

def collect_conf_correct(mode: str, traces, judge):
    det = DETECTORS[mode]
    confs, correct = [], []
    for t in traces:
        d = det.detect(redact(t), judge, threshold=0.0)   # threshold 0 to collect the full score range
        if d is not None:
            confs.append(d.confidence)
            correct.append(mode in t.injected_labels)
    return confs, correct

def run_published(n: int = 1000, seed: int = 7, out_dir: str = "reports/out", judge=None) -> dict:
    if judge is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("SKIP: set ANTHROPIC_API_KEY to produce published numbers.")
            return {"skipped": True}
        from detector.judge import ClaudeJudge
        judge = ClaudeJudge(api_key=os.environ["ANTHROPIC_API_KEY"])
    ds = generate_dataset(n=n, seed=seed, held_out=True)     # held-out phrasings: the anti-circularity slice
    per_mode = {m: eval_mode(m, ds, judge) for m in ("phantom_action", "ungrounded", "misrouting")}
    confs, correct = collect_conf_correct("phantom_action", ds, judge)
    reliability = reliability_bins(confs, correct)
    transfer = eval_mode("phantom_action", load_transfer(), judge)
    ab = ablation(ds, judge)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "published.md"), "w", encoding="utf-8") as fh:
        fh.write("# Published numbers (ClaudeJudge, held-out)\n\n")
        for m, r in per_mode.items():
            fh.write(f"## {m}\ncounts={r['counts']} rates={r['rates']} kappa={r['kappa']:.3f} "
                     f"hard_neg_fp={r['hard_negative_fp']}\n\n")
        fh.write(f"## transfer (phantom)\ncounts={transfer['counts']} rates={transfer['rates']}\n\n")
        fh.write(f"## ablation\n{ab}\n\n## reliability\n{reliability}\n")
    return {"per_mode": per_mode, "transfer": transfer, "ablation": ab, "reliability": reliability}

if __name__ == "__main__":
    run_published()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_published.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Produce the real numbers (manual, keyed)**

Run (with your key set): `python -m eval.published` → writes `reports/out/published.md` with the **ClaudeJudge** numbers. This file — not any StubJudge output — feeds Task 18.

- [ ] **Step 6: Commit**

```bash
git add eval/published.py tests/test_published.py
git commit -m "feat(eval): ClaudeJudge published-numbers run — P/R/F1, kappa, ablation, transfer, reliability"
```

---

### Task 18: Case study + docs refresh (numbers from Task 17)

**Files:**
- Create: `docs/case-study.md`
- Modify: `README.md` (paste the real `reports/out/published.md` eval block; mark v1 build order done)

**Interfaces:** none (documentation).

- [ ] **Step 1: Gather the ClaudeJudge numbers** from `reports/out/published.md` (Task 17 Step 5) and the top pattern from `reports/out/report.md`.
- [ ] **Step 2: Write `docs/case-study.md`** — the Monday-morning phantom-dispute narrative, then paste: composition stats, per-mode P/R/F1 + κ (from ClaudeJudge), the hard-negative FP, the ablation table, the transfer-set result, the reliability diagram summary, the intent→action confusion, and the guardrail before/after. Show the dispute-phantom, the cancel-subscription-phantom, **and** a misrouting pattern as ranked patterns (generality + all three detectors). Close with the tradeoffs (spec §8) and the detection ceiling (spec §5). **Two honesty caveats to state explicitly:** (a) the ranked-report snapshot and every metric must come from a **keyed `ClaudeJudge` run** (`reports/out/published.md` and a ClaudeJudge report run) — the StubJudge `report.md` is phantom-only and is the CI smoke path, not a result; (b) v1 `threshold_for` uses fixed per-severity constants — the reliability diagram is *reported* but not yet *fed back* into the thresholds (isotonic calibration is the v2 `[calibrate]` upgrade), so describe thresholds as "severity-tiered," not "auto-calibrated."
- [ ] **Step 3: Update README** — paste the ClaudeJudge eval block; mark v1 build-order items done.
- [ ] **Step 4: Commit**

```bash
git add docs/case-study.md README.md
git commit -m "docs: v1 case study with ClaudeJudge numbers + README refresh"
```

---

## Self-review (against the v3 spec + the two review passes)

- **Spec coverage:** schema/redaction (T1–T2, impr 5 at the parser boundary) · tools+CONFIRM (T3) · phrasings/held-out (T4, impr 4) · generator with **two verticals + flagged hard negatives** (T5) · features (T6) · judge with provenance (T7) · calibration/per-severity thresholds (T8, impr 1) · Detector protocol+registry+grounding (T9, impr 2) · unified metrics+κ (T10) · ungrounded (T11) · routing+intent→action (T12) · ablation+transfer (T13, impr 4) · non-tautological guardrail (T14) · stable-id group-by + cost-overlay ranking (T15, impr 3) · regression+CLI (T16) · **ClaudeJudge published numbers** (T17) · case study from real numbers (T18).
- **Review findings addressed:** ClaudeJudge is now a gating task feeding the case study (PM #1); `cancel_subscription` phantom slice makes generality real (PM #3); κ computed in T10/T17 (PM #2); routing wired into `run_v1` + confusion (PM #6); calibration curve produced from ClaudeJudge confidences (PM #4); Detector registry (Eng #1); `Detection.severity` + `Verdict.model/prompt/usage` + `Trace.timestamp/deploy_id` + `signature_id` (Eng #2–4,6); redact-once-at-parser and `grounds` vs the redacted trace (Eng #5, bug #3); `threshold_for` wired into detectors (Eng #2); guardrail structural-trigger vs text-measure (bug #1); signature tool from the actual `ToolCall` (bug #2); hard-neg via `is_hard_negative` flag (Eng #7); one `CONFIRM_WORDS` constant (Eng #8).
- **Deferred by design (named, not built):** v2 monitor (streaming/alerts/sampling-at-scale) — the schema fields and judge `usage` seam are reserved for it; v3 inline guardrail; sklearn isotonic calibration (the `[calibrate]` extra); the semantic-wrong detection ceiling.
- **Type consistency:** `Verdict` and `Detection` (with `severity`) are used identically T7–T18; `DETECTORS` registry contract stable from T9; `eval_mode`/`confusion`/`prf`/`cohen_kappa` shapes stable from T10; `group` returns `{signature_id: {signature, members}}` consumed identically by `rank`/`render`.
- **Not gold-plated (per the engineer's guard):** no judge factory, no clustering abstraction, no sklearn in v1, StubJudge stays phantom-only.
