GUARDRAILS = {
    "phantom_action": "Don't confirm a dispute unless file_dispute returns a dispute_id.",
    "error_masking": "Don't claim 'processed' on any non-2xx tool result; surface a handoff.",
    "ungrounded": "Don't state a policy figure without a retrieved chunk above score tau; cite it.",
    "misrouting": "Re-confirm intent before any state-changing tool call when routing confidence < tau.",
}
