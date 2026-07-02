# routing/routing.py
from __future__ import annotations
from parser.schema import Trace
from generator.tools import correct_tool
from routing.intent import infer_intent


def _first_user_text(trace: Trace) -> str | None:
    for turn in trace.turns:
        if turn.role == "user":
            return turn.text
    return None


def routing_mismatch(trace: Trace) -> bool:
    """HONEST misrouting decision (detection path).

    Infers the user's intended intent from the FIRST user turn's text — an observable
    field a real trace carries — and fires when the tool(s) actually invoked do not
    match correct_tool(inferred_intent). NEVER reads trace.intent_true (that would be
    circular: grading against the answer key). Returns False when:
      - the user issued a mid-conversation correction (legit intent change, not a misroute), or
      - intent cannot be confidently inferred (no guessing → no manufactured false positive), or
      - no tool was called (nothing to compare against).
    """
    if trace.behavioral_signals.get("user_correction"):
        return False
    inferred = infer_intent(_first_user_text(trace))
    if inferred is None:
        return False
    expected = correct_tool(inferred)
    calls = [c for turn in trace.turns for c in turn.tool_calls]
    if not calls:
        return False
    return any(c.name != expected for c in calls)


def intent_action_confusion(traces) -> dict:
    """EVAL/reporting confusion matrix. This is an eval artifact, NOT part of the
    detection path, so it is permitted to use ground-truth intent_true as its axis."""
    table: dict[tuple, int] = {}
    for t in traces:
        served = correct_tool(t.intent_routed) if t.intent_routed in ("dispute_charge", "request_refund",
                 "check_balance", "cancel_subscription", "policy_question") else t.intent_routed
        key = (t.intent_true, served)
        table[key] = table.get(key, 0) + 1
    return table
