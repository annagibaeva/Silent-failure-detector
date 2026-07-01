# eval/regression.py
from eval.harness import load_transfer, eval_mode

PHANTOM_RECALL_FLOOR = 0.8

def check_regression(judge) -> dict:
    res = eval_mode("phantom_action", load_transfer(), judge)
    return {"phantom_recall": res["rates"]["recall"], "floor": PHANTOM_RECALL_FLOOR, "counts": res["counts"]}
