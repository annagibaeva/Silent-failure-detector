from generator.generate import generate_dataset
from detector.judge import StubJudge
from eval.harness import eval_mode

def test_phantom_eval_counts_and_hard_neg_fp():
    ds = generate_dataset(n=300, seed=2)
    res = eval_mode("phantom_action", ds, StubJudge())
    assert set(res["counts"]) == {"tp", "fp", "fn", "tn"}
    # HONEST baseline (post FIX2): the CONFIRM_WORDS heuristic / StubJudge now MISS the
    # confirm-word-free (euphemistic) phantom minority, so recall is < 1.0 and FN > 0.
    # Observed 0.867 (26/30) at seed=2; band has headroom above the 0.8 regression floor.
    assert res["counts"]["fn"] > 0             # heuristic misses euphemistic phantoms -> no tautology
    assert 0.82 <= res["rates"]["recall"] <= 0.95
    assert res["hard_negative_fp"] == 0        # hard negatives (tool succeeded) must not flag
