from __future__ import annotations
from parser.schema import Trace
from generator.tools import correct_tool
from routing.intent import infer_intent

LATENCY_TIMEOUT_MS = 1000
RETRIEVAL_TAU = 0.5

def _first_user_text(trace: Trace) -> str | None:
    for turn in trace.turns:
        if turn.role == "user":
            return turn.text
    return None

def extract(trace: Trace) -> dict:
    calls = [c for turn in trace.turns for c in turn.tool_calls]
    # HONEST intent_tool_mismatch: infer the user's intent from their utterance (observable)
    # rather than reading trace.intent_true (the ground-truth answer key). None inference
    # means we cannot confidently say the tool is wrong, so the signal stays False.
    inferred = infer_intent(_first_user_text(trace))
    return {
        "any_tool_failed": any(c.result.get("success") is False for c in calls),
        "null_result": any(c.result in (None, {}) for c in calls),
        "low_retrieval_score": any(
            c.retrieved is not None and (not c.retrieved or max(r["score"] for r in c.retrieved) < RETRIEVAL_TAU)
            for c in calls),
        "over_latency": any(c.latency_ms > LATENCY_TIMEOUT_MS for c in calls),
        "intent_tool_mismatch": (inferred is not None
                                 and any(c.name != correct_tool(inferred) for c in calls)) if calls else False,
    }
