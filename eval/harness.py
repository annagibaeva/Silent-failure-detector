import json

from parser.schema import Trace
from parser.redact import redact
from eval.metrics import confusion, prf, cohen_kappa
from detector.detect import DETECTORS
from features.heuristics import extract
from generator.tools import CONFIRM_WORDS

def eval_mode(mode: str, traces, judge, threshold=None) -> dict:
    det = DETECTORS[mode]
    y_true = [mode in t.injected_labels for t in traces]
    y_pred = [det.detect(redact(t), judge, threshold) is not None for t in traces]
    counts = confusion(y_true, y_pred)
    hard_neg_fp = sum(1 for t, p in zip(traces, y_pred) if p and t.is_hard_negative)
    return {"mode": mode, "counts": counts, "rates": prf(counts),
            "kappa": cohen_kappa(y_true, y_pred), "hard_negative_fp": hard_neg_fp, "n": len(traces)}


def load_transfer(path: str = "fixtures/transfer.jsonl") -> list[Trace]:
    with open(path, encoding="utf-8") as fh:
        return [Trace.from_dict(json.loads(line)) for line in fh if line.strip()]


def _heuristics_only_pred(trace: Trace) -> bool:
    agents = [t for t in trace.turns if t.role == "agent"]
    confident = bool(agents) and any(w in agents[-1].text.lower() for w in CONFIRM_WORDS)
    return extract(trace)["any_tool_failed"] and confident


def ablation(traces, judge) -> dict:
    y_true = ["phantom_action" in t.injected_labels for t in traces]
    heur = [_heuristics_only_pred(t) for t in traces]
    hybrid = [DETECTORS["phantom_action"].detect(redact(t), judge) is not None for t in traces]

    heur_counts = confusion(y_true, heur)
    hybrid_counts = confusion(y_true, hybrid)
    return {
        "heuristics_only": {"counts": heur_counts, "rates": prf(heur_counts)},
        "hybrid": {"counts": hybrid_counts, "rates": prf(hybrid_counts)},
    }
