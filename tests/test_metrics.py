from eval.metrics import confusion, prf, cohen_kappa

def test_confusion_prf_kappa():
    c = confusion([True, True, False, False], [True, False, False, False])
    assert c == {"tp": 1, "fp": 0, "fn": 1, "tn": 2}
    assert prf(c)["precision"] == 1.0 and prf(c)["recall"] == 0.5
    assert cohen_kappa([True, False], [True, False]) == 1.0
