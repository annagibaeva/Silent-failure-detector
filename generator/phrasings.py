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
