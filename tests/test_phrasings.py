from generator.phrasings import phantom_claims, phrasings_for

def test_dev_heldout_disjoint_per_intent():
    for intent in ("dispute_charge", "cancel_subscription"):
        dev, held = set(phantom_claims(intent, False)), set(phantom_claims(intent, True))
        assert dev and held and dev.isdisjoint(held)
    assert set(phrasings_for("ungrounded", False)).isdisjoint(set(phrasings_for("ungrounded", True)))
