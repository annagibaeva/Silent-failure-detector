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
