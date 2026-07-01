# tests/test_routing.py
from parser.schema import Trace, Turn, ToolCall
from parser.redact import redact
from routing.routing import routing_mismatch
from detector.detect import DETECTORS

def _misrouted():
    call = ToolCall("issue_refund", {"txn_id": "t"}, {"success": True}, "ok", 100, None)
    return Trace("m_1", "dispute_charge", "request_refund", ["misrouting"],
                 [Turn("user", "dispute this charge"), Turn("agent", "Refund processed.", [call])],
                 {"user_reask": False, "user_correction": False, "abandoned": False}, True, None)

def test_flags_intent_action_mismatch():
    assert routing_mismatch(_misrouted()) is True

def test_routing_detector_registered():
    d = DETECTORS["misrouting"].detect(redact(_misrouted()), judge=None)
    assert d is not None and d.failure_mode == "misrouting"
