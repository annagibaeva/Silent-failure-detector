from generator.generate import generate_dataset, composition
from parser.schema import validate

def test_valid_balanced_two_vertical():
    ds = generate_dataset(n=300, seed=1)
    assert all(validate(t) == [] for t in ds)
    comp = composition(ds)
    assert 0.75 <= comp["clean_fraction"] <= 0.85
    intents = {t.intent_true for t in ds if "phantom_action" in t.injected_labels}
    assert {"dispute_charge", "cancel_subscription"} <= intents  # generality is real
    assert any("misrouting" in t.injected_labels for t in ds)    # routing has synthetic positives

def test_hard_negatives_flagged_and_labeled_clean():
    ds = generate_dataset(n=300, seed=1)
    hard = [t for t in ds if t.is_hard_negative]
    assert hard
    assert all(t.injected_labels == [] for t in hard)          # look failure-ish, are fine
    assert all(t.turns[-1].tool_calls[0].result.get("success") is True for t in hard)
