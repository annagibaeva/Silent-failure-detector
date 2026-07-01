from __future__ import annotations
from generator.tools import SEVERITY

def rank(groups, cost_weights=None) -> list[dict]:
    cost_weights = cost_weights or {}
    rows = []
    for sid, g in groups.items():
        mode = g["signature"][0]
        freq = len(g["members"])
        weight = cost_weights.get(mode, 1.0)
        rows.append({"signature_id": sid, "signature": g["signature"], "freq": freq,
                     "severity": SEVERITY[mode], "cost_weight": weight,
                     "score": freq * SEVERITY[mode] * weight})
    return sorted(rows, key=lambda r: r["score"], reverse=True)
