from generator.generate import generate_dataset
from detector.judge import StubJudge
from eval.harness import eval_mode

def test_phantom_eval_counts_and_hard_neg_fp():
    ds = generate_dataset(n=300, seed=2)
    res = eval_mode("phantom_action", ds, StubJudge())
    assert set(res["counts"]) == {"tp", "fp", "fn", "tn"}
    assert res["rates"]["recall"] > 0.8
    assert res["hard_negative_fp"] == 0        # hard negatives (tool succeeded) must not flag
