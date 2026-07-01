from parser.schema import Trace
from features.heuristics import extract
from tests.test_schema import RAW

def test_tool_failure_signal():
    f = extract(Trace.from_dict(RAW))
    assert f["any_tool_failed"] is True and f["intent_tool_mismatch"] is False
