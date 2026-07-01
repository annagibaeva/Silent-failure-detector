from parser.schema import Trace
from parser.redact import redact
from tests.test_schema import RAW

def test_redacts_args_and_text_but_keeps_structure():
    r = redact(Trace.from_dict(RAW))
    tc = r.turns[1].tool_calls[0]
    assert tc.args["txn_id"] == "<txn_id>"
    assert tc.result["success"] is False and tc.result["error"] == "txn_not_found"
    assert "txn_8842" not in (r.turns[0].text + r.turns[1].text)
