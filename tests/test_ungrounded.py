# tests/test_ungrounded.py
from parser.schema import Trace, Turn, ToolCall
from parser.redact import redact
from detector.detect import DETECTORS
from detector.judge import Verdict

class _UngroundedJudge:
    def assess(self, q, t): return Verdict("ungrounded", 0.9, "60 days")

def _policy():
    call = ToolCall("policy_search", {"query": "dispute window"}, {"success": True}, "ok", 120,
                    retrieved=[{"chunk_id": "k1", "text": "window is 90 days", "score": 0.2}])
    return Trace("u_1", "policy_question", "policy_question", ["ungrounded"],
                 [Turn("user", "how long to dispute?"), Turn("agent", "Our dispute window is 60 days.", [call])],
                 {"user_reask": False, "user_correction": False, "abandoned": False}, True, None)

def test_ungrounded_via_registry():
    d = DETECTORS["ungrounded"].detect(redact(_policy()), _UngroundedJudge())
    assert d is not None and d.failure_mode == "ungrounded" and d.severity == 3


class _SilentJudge:
    """Correct judge: the claim IS grounded (matches the retrieved chunk), so no failure."""
    def assess(self, q, t):
        return Verdict(None, 0.1, "")

def _grounded_policy():
    # Retrieval score ABOVE RETRIEVAL_TAU (0.5) and the agent claim matches the chunk verbatim.
    call = ToolCall("policy_search", {"query": "dispute window"}, {"success": True}, "ok", 120,
                    retrieved=[{"chunk_id": "k1", "text": "the dispute window is 90 days", "score": 0.9}])
    return Trace("u_ok", "policy_question", "policy_question", [],
                 [Turn("user", "how long to dispute?"),
                  Turn("agent", "Our dispute window is 90 days.", [call])],
                 {"user_reask": False, "user_correction": False, "abandoned": False}, True, None)

def test_ungrounded_stays_silent_on_grounded_case():
    # Precision lock-in: a grounded claim (score>tau, matches chunk) must NOT be flagged.
    d = DETECTORS["ungrounded"].detect(redact(_grounded_policy()), _SilentJudge())
    assert d is None
