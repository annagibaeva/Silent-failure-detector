from parser.schema import Trace, validate

RAW = {
    "conversation_id": "c_001", "intent_true": "dispute_charge", "intent_routed": "dispute_charge",
    "injected_labels": ["phantom_action"],
    "turns": [
        {"role": "user", "text": "dispute a $50 charge", "tool_calls": []},
        {"role": "agent", "text": "Your dispute has been filed.",
         "tool_calls": [{"name": "file_dispute", "args": {"txn_id": "txn_8842"},
                          "result": {"success": False, "error": "txn_not_found"},
                          "status": "ok", "latency_ms": 220, "retrieved": None}]},
    ],
    "behavioral_signals": {"user_reask": False, "user_correction": False, "abandoned": False},
    "resolved": True, "csat": None, "timestamp": None, "deploy_id": None, "is_hard_negative": False,
}

def test_roundtrip_preserves_fields():
    t = Trace.from_dict(RAW)
    assert t.intent_true == "dispute_charge"
    assert t.turns[1].tool_calls[0].result["success"] is False
    assert t.to_dict() == RAW

def test_missing_optionals_default_and_validate_clean():
    minimal = {k: v for k, v in RAW.items() if k not in ("timestamp", "deploy_id", "is_hard_negative")}
    t = Trace.from_dict(minimal)
    assert t.timestamp is None and t.is_hard_negative is False
    assert validate(t) == []
