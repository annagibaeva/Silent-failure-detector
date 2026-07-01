# tests/test_published.py
from generator.generate import generate_dataset
from eval.published import run_published
from detector.judge import StubJudge

def test_run_published_shape_with_injected_judge(tmp_path):
    out = run_published(n=200, seed=7, out_dir=str(tmp_path), judge=StubJudge())
    assert not out.get("skipped")
    assert "phantom_action" in out["per_mode"]
    assert "reliability" in out and "ablation" in out
    assert set(out["per_mode"]["phantom_action"]["counts"]) == {"tp", "fp", "fn", "tn"}
