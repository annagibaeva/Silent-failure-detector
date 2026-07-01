from parser.redact import redact
from eval.metrics import confusion, prf, cohen_kappa
from detector.detect import DETECTORS

def eval_mode(mode: str, traces, judge, threshold=None) -> dict:
    det = DETECTORS[mode]
    y_true = [mode in t.injected_labels for t in traces]
    y_pred = [det.detect(redact(t), judge, threshold) is not None for t in traces]
    counts = confusion(y_true, y_pred)
    hard_neg_fp = sum(1 for t, p in zip(traces, y_pred) if p and t.is_hard_negative)
    return {"mode": mode, "counts": counts, "rates": prf(counts),
            "kappa": cohen_kappa(y_true, y_pred), "hard_negative_fp": hard_neg_fp, "n": len(traces)}
