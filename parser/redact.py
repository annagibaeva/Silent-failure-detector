from __future__ import annotations
import copy, re
from parser.schema import Trace

_PII_ARG_KEYS = {"txn_id", "account_id", "card_id", "name", "address"}
_ID_RE = re.compile(r"\b(txn|acct|account|card)_[A-Za-z0-9]+\b", re.IGNORECASE)

def _placeholder_for(key: str) -> str:
    return f"<{'txn_id' if key.startswith('txn') else key}>"

def _redact_text(text: str) -> str:
    return _ID_RE.sub(lambda m: f"<{m.group(1).lower().replace('acct', 'account')}_id>", text)

def redact(trace: Trace) -> Trace:
    t = copy.deepcopy(trace)
    for turn in t.turns:
        turn.text = _redact_text(turn.text)
        for call in turn.tool_calls:
            for k in list(call.args):
                if k in _PII_ARG_KEYS:
                    call.args[k] = _placeholder_for(k)
    return t
