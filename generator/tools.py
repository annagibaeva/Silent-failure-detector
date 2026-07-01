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
