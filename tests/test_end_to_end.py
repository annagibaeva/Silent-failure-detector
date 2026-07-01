# tests/test_end_to_end.py
import os
from run_v1 import main

def test_end_to_end_writes_report(tmp_path):
    out = main(n=300, seed=5, out_dir=str(tmp_path))
    assert os.path.exists(out["report_path"])
    assert out["eval"]["phantom_action"]["rates"]["recall"] > 0.8
    assert "misrouting" in out["eval"]
