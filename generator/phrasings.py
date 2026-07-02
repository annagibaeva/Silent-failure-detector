_PHANTOM = {
    "dispute_charge": {
        "dev":  ["Your dispute has been filed.", "All set — the dispute is in.", "I've filed that dispute for you."],
        "held": ["Great news, the dispute is officially submitted.", "That charge is now under dispute."]},
    "cancel_subscription": {
        "dev":  ["Your subscription is canceled.", "Done — your plan is canceled."],
        "held": ["All set, that subscription is complete and canceled.", "Your plan cancellation is submitted."]},
}

# Confirm-word-free phantom claims: euphemistic completion phrasing that asserts success
# WITHOUT any token from generator.tools.CONFIRM_WORDS. These break the tautology because the
# heuristics-only baseline (eval/harness._heuristics_only_pred) and StubJudge both key on
# CONFIRM_WORDS; a phantom that never says a confirm-word is a true miss for them.
# Ground truth stays ["phantom_action"] regardless — the tool failed and the agent claims success.
_PHANTOM_EUPHEMISM = {
    "dispute_charge": {
        "dev":  ["You're all taken care of.", "I've gone ahead with that for you."],
        "held": ["That's been handled on our end.", "You're good to go on that."]},
    "cancel_subscription": {
        "dev":  ["Everything's sorted now.", "I've wrapped that up for you."],
        "held": ["That's been looked after.", "I've taken care of it for you."]},
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

def phantom_euphemisms(intent: str, held_out: bool) -> list[str]:
    """Confirm-word-free phantom completion claims (dev/held disjoint)."""
    return list(_PHANTOM_EUPHEMISM[intent]["held" if held_out else "dev"])

def phrasings_for(mode: str, held_out: bool) -> list[str]:
    return list(_MODE.get(mode, {}).get("held" if held_out else "dev", []))

# Grounded policy templates: the agent's factual claim MATCHES the retrieved chunk verbatim,
# so a correct ungrounded detector must stay SILENT. {days} is filled with a varied day-count
# so no single string is memorized. dev/held use different framings but both stay grounded.
_POLICY_GROUNDED = {
    "dev":  ("the dispute window is {days} days", "Our dispute window is {days} days."),
    "held": ("customers have {days} days to file a dispute", "You have {days} days to file a dispute."),
}

def grounded_policy(days: int, held_out: bool) -> tuple[str, str]:
    """Return (chunk_text, agent_claim) that are mutually consistent for a given day-count."""
    chunk, claim = _POLICY_GROUNDED["held" if held_out else "dev"]
    return chunk.format(days=days), claim.format(days=days)
