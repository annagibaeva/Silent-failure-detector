# tests/test_regression.py
from eval.regression import check_regression
from detector.judge import StubJudge

def test_regression_floor_holds():
    res = check_regression(StubJudge())
    assert res["phantom_recall"] >= res["floor"]
