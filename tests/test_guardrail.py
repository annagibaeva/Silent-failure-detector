from parser.schema import Trace
from guardrails.phantom import apply_phantom_guardrail, before_after
from tests.test_schema import RAW

def test_rewrites_structural_phantom_to_handoff():
    fixed = apply_phantom_guardrail(Trace.from_dict(RAW))   # file_dispute, no dispute_id
    assert "filed" not in fixed.turns[-1].text.lower() and "connect you" in fixed.turns[-1].text.lower()

def test_before_after_reduces_dispute_phantom_claims():
    ba = before_after(n=300, seed=3)
    assert ba["phantom_confirmation_rate_off"] > ba["phantom_confirmation_rate_on"]
    assert ba["phantom_confirmation_rate_on"] == 0.0
