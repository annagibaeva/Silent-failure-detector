GUARDRAILS = {
    "phantom_action": "Don't confirm a dispute unless file_dispute returns a dispute_id.",
    "error_masking": "Don't claim 'processed' on any non-2xx tool result; surface a handoff.",
    "ungrounded": "Don't state a policy figure without a retrieved chunk above score tau; cite it.",
    "misrouting": "Re-confirm intent before any state-changing tool call when routing confidence < tau.",
}

# Tool-specific guardrail overrides. Some failure types (e.g. phantom_action)
# apply to multiple tools whose correct guardrail wording differs by tool. When
# a signature's tool appears here, this text takes precedence over the
# failure-type default in GUARDRAILS.
GUARDRAILS_BY_TOOL = {
    "cancel_subscription": "Don't confirm a cancellation unless cancel_subscription returns billing stopped (e.g. billing_active is false / a cancellation id is returned).",
}


def guardrail_for(failure_type: str, tool: str) -> str:
    """Return the guardrail text for a signature, preferring a tool-specific
    override before falling back to the failure-type default."""
    if tool in GUARDRAILS_BY_TOOL:
        return GUARDRAILS_BY_TOOL[tool]
    return GUARDRAILS.get(failure_type, "n/a")
