# tests/test_judge.py
from parser.schema import Trace
from detector.judge import StubJudge, Verdict
from tests.test_schema import RAW

def test_stub_flags_phantom_and_grounds_span():
    v = StubJudge().assess("phantom?", Trace.from_dict(RAW))
    assert isinstance(v, Verdict) and v.failure_mode == "phantom_action"
    assert v.evidence_span in RAW["turns"][1]["text"]
    assert v.model_version == "stub" and 0.0 <= v.confidence <= 1.0
