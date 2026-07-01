# tests/test_detect.py
from parser.schema import Trace
from parser.redact import redact
from detector.detect import DETECTORS, grounds
from detector.judge import StubJudge, Verdict
from tests.test_schema import RAW

class _UngroundedJudge:
    def assess(self, q, t): return Verdict("phantom_action", 0.99, "NOT IN THE TRACE")

def test_phantom_detector_via_registry():
    tr = redact(Trace.from_dict(RAW))
    d = DETECTORS["phantom_action"].detect(tr, StubJudge())   # threshold=None -> threshold_for
    assert d is not None and d.failure_mode == "phantom_action" and d.severity == 5
    assert "any_tool_failed" in d.heuristics_hit

def test_rejects_ungrounded_verdict():
    tr = redact(Trace.from_dict(RAW))
    assert DETECTORS["phantom_action"].detect(tr, _UngroundedJudge()) is None
