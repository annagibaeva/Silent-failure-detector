from detector.judge import StubJudge
from eval.harness import ablation, load_transfer
from parser.schema import validate


def test_transfer_loads_labeled():
    ts = load_transfer()
    assert len(ts) == 15
    assert all(isinstance(t.injected_labels, list) for t in ts)
    assert all(validate(t) == [] for t in ts)


def test_ablation_two_rows():
    ab = ablation(load_transfer(), StubJudge())
    assert set(ab) == {"heuristics_only", "hybrid"} and "rates" in ab["hybrid"]
