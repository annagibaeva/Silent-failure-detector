# routing/intent.py
"""Deterministic, keyword/rule-based intent inference from the USER's message text.

This is the HONEST replacement for reading `trace.intent_true` in the misrouting
detection path. A real production trace carries the user's utterance but NEVER the
ground-truth intent label; so the detector infers what the user wanted from what the
user actually said, then compares it to the tool that was invoked.

Returns an INTENTS key (see generator.tools.INTENTS) or None when no rule matches
confidently. None means "don't fire" — we never guess when the utterance is
underspecified, to avoid manufacturing false positives.
"""
from __future__ import annotations
import re

# Ordered rules: (intent_key, list-of-regex-keyword-patterns). Evaluated top-to-bottom;
# the FIRST intent with any matching pattern wins. Order matters where phrasings overlap
# (e.g. a policy_question about disputing must beat the dispute_charge rule), so the more
# specific "how long / window" policy cues are checked before the generic "dispute" cue.
_RULES: list[tuple[str, list[str]]] = [
    # Policy questions FIRST: "how long do I have to dispute?", "what's the dispute window?"
    ("policy_question", [
        r"\bhow long\b",
        r"\bdispute window\b",
        r"\bwhat'?s the (?:policy|window)\b",
        r"\bwhat is the (?:policy|window)\b",
        r"\bpolicy\b",
        r"\bhow many days\b",
    ]),
    ("cancel_subscription", [
        r"\bcancel\b",
        r"\bunsubscribe\b",
        r"\bend my (?:plan|subscription)\b",
    ]),
    ("request_refund", [
        r"\brefund\b",
        r"\bmoney back\b",
        r"\breimburse\b",
    ]),
    ("dispute_charge", [
        r"\bdispute\b",
        r"\bcharge i didn'?t make\b",
        r"\bdidn'?t (?:make|authorize)\b",
        r"\bunauthori[sz]ed\b",
        r"\bfraud(?:ulent)?\b",
    ]),
    ("check_balance", [
        r"\bbalance\b",
        r"\bhow much do i have\b",
        r"\bhow much is (?:in |on )?my\b",
    ]),
]

_COMPILED: list[tuple[str, list[re.Pattern]]] = [
    (intent, [re.compile(p, re.IGNORECASE) for p in pats]) for intent, pats in _RULES
]


def infer_intent(user_text: str | None) -> str | None:
    """Infer the user's intended INTENTS key from their utterance, or None if no
    confident keyword match. Purely observable-input based (never reads ground truth)."""
    if not user_text:
        return None
    for intent, patterns in _COMPILED:
        if any(p.search(user_text) for p in patterns):
            return intent
    return None
