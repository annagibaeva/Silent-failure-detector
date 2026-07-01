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
