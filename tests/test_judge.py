# tests/test_judge.py
from parser.schema import Trace
from detector.judge import StubJudge, Verdict, CachingJudge
from tests.test_schema import RAW

def test_stub_flags_phantom_and_grounds_span():
    v = StubJudge().assess("phantom?", Trace.from_dict(RAW))
    assert isinstance(v, Verdict) and v.failure_mode == "phantom_action"
    assert v.evidence_span in RAW["turns"][1]["text"]
    assert v.model_version == "stub" and 0.0 <= v.confidence <= 1.0

def test_judge_dict_hides_ground_truth_but_keeps_conversation():
    t = Trace.from_dict(RAW)
    jd = t.to_judge_dict()
    # ground-truth annotations must never reach the judge
    for leaked in ("intent_true", "injected_labels", "is_hard_negative"):
        assert leaked not in jd
    # everything the judge legitimately needs is preserved
    assert jd["conversation_id"] == RAW["conversation_id"]
    assert jd["intent_routed"] == RAW["intent_routed"]
    assert jd["turns"] == RAW["turns"]
    assert "behavioral_signals" in jd and "resolved" in jd
    # the scoring view (to_dict) is untouched
    assert t.to_dict() == RAW

def test_caching_judge_reuses_verdict():
    calls = {"n": 0}
    class _CountingJudge:
        def assess(self, question, trace):
            calls["n"] += 1
            return Verdict(None, 0.5, "")
    cached = CachingJudge(_CountingJudge())
    tr = Trace.from_dict(RAW)
    cached.assess("q?", tr)
    cached.assess("q?", tr)
    assert calls["n"] == 1
    assert cached.cache_hits == 1
