from cluster.groupby import group
from detector.detect import Detection
from parser.schema import Trace
from tests.test_schema import RAW

def test_same_signature_groups_and_uses_actual_tool():
    tr = Trace.from_dict(RAW)
    d = Detection("c_001", "phantom_action", 5, 0.9, "filed", ["any_tool_failed"])
    g = group([(d, tr), (d, tr)])
    assert len(g) == 1
    only = next(iter(g.values()))
    assert only["signature"][2] == "file_dispute"   # actual tool from the ToolCall
    assert len(only["members"]) == 2
