from __future__ import annotations
import hashlib

def _relevant_call(trace):
    for turn in reversed(trace.turns):
        if turn.tool_calls:
            return turn.tool_calls[-1]
    return None

def _error_type(call) -> str:
    if call is None:
        return "none"
    if call.result.get("success") is False:
        return call.result.get("error", "unknown")
    if call.retrieved is not None:
        return "low_score"
    return "none"

def signature(detection, trace) -> tuple:
    call = _relevant_call(trace)
    tool = call.name if call else "none"                     # actual tool taken, not correct_tool
    return (detection.failure_mode, trace.intent_true, tool, _error_type(call), detection.evidence_span[:40])

def signature_id(sig: tuple) -> str:
    key = "|".join(str(x) for x in sig[:4])                  # structural only; drop volatile claim snippet
    return hashlib.sha1(key.encode()).hexdigest()[:12]

def group(pairs) -> dict:
    out: dict[str, dict] = {}
    for det, tr in pairs:
        sig = signature(det, tr)
        sid = signature_id(sig)
        out.setdefault(sid, {"signature": sig, "members": []})["members"].append((det, tr))
    return out
