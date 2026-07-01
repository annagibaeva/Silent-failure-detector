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
