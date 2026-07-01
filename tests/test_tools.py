from generator.tools import INTENTS, SEVERITY, correct_tool, CONFIRM_WORDS

def test_surface_and_severity():
    assert correct_tool("dispute_charge") == "file_dispute"
    assert correct_tool("cancel_subscription") == "cancel_subscription"
    assert SEVERITY["phantom_action"] == 5 > SEVERITY["ungrounded"]

def test_confirm_words_cover_dev_and_heldout_phantom_language():
    for w in ("filed", "submitted", "under dispute", "canceled"):
        assert w in CONFIRM_WORDS
