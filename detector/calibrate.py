# detector/calibrate.py
from __future__ import annotations
from generator.tools import SEVERITY

def reliability_bins(confidences, correct, n_bins: int = 10) -> list[dict]:
    bins = []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        idx = [j for j, c in enumerate(confidences) if lo <= c < hi or (hi == 1.0 and c == 1.0)]
        if idx:
            bins.append({"lo": lo, "hi": hi, "n": len(idx),
                         "mean_conf": sum(confidences[j] for j in idx) / len(idx),
                         "accuracy": sum(1 for j in idx if correct[j]) / len(idx)})
        else:
            bins.append({"lo": lo, "hi": hi, "n": 0, "mean_conf": 0.0, "accuracy": 0.0})
    return bins

def select_threshold(confidences, correct, objective: str, floor: float) -> float:
    candidates = sorted(set(confidences))
    if not candidates:
        return 0.5
    for thr in (candidates if objective == "recall" else list(reversed(candidates))):
        pred = [c >= thr for c in confidences]
        tp = sum(1 for p, y in zip(pred, correct) if p and y)
        fp = sum(1 for p, y in zip(pred, correct) if p and not y)
        fn = sum(1 for p, y in zip(pred, correct) if not p and y)
        value = (tp / (tp + fn) if objective == "recall" and (tp + fn) else
                 tp / (tp + fp) if (tp + fp) else 0.0)
        if value >= floor:
            return thr
    return candidates[-1]

def threshold_for(mode: str) -> float:
    """Critical/High -> recall-first (low); Medium -> balanced; Low -> precision-first (high)."""
    sev = SEVERITY[mode]
    return 0.3 if sev >= 4 else 0.5 if sev == 3 else 0.8
