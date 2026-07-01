# tests/test_calibrate.py
from detector.calibrate import select_threshold, threshold_for

def test_recall_objective_low_threshold():
    thr = select_threshold([0.2, 0.4, 0.6, 0.8, 0.95], [False, False, True, True, True],
                           objective="recall", floor=0.95)
    assert thr <= 0.6

def test_critical_is_recall_first():
    assert threshold_for("phantom_action") < threshold_for("clarification_loop")
