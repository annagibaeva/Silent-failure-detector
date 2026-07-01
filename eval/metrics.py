def confusion(y_true, y_pred) -> dict:
    return {
        "tp": sum(1 for t, p in zip(y_true, y_pred) if t and p),
        "fp": sum(1 for t, p in zip(y_true, y_pred) if not t and p),
        "fn": sum(1 for t, p in zip(y_true, y_pred) if t and not p),
        "tn": sum(1 for t, p in zip(y_true, y_pred) if not t and not p),
    }

def prf(c: dict) -> dict:
    p = c["tp"] / (c["tp"] + c["fp"]) if (c["tp"] + c["fp"]) else 0.0
    r = c["tp"] / (c["tp"] + c["fn"]) if (c["tp"] + c["fn"]) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": p, "recall": r, "f1": f1}

def cohen_kappa(y_true, y_pred) -> float:
    c = confusion(y_true, y_pred)
    n = sum(c.values())
    if not n:
        return 0.0
    po = (c["tp"] + c["tn"]) / n
    pe = (((c["tp"] + c["fp"]) * (c["tp"] + c["fn"])) + ((c["fn"] + c["tn"]) * (c["fp"] + c["tn"]))) / (n * n)
    return (po - pe) / (1 - pe) if (1 - pe) else 0.0
