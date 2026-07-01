# run_v1.py
from __future__ import annotations
import os
from generator.generate import generate_dataset
from parser.redact import redact
from detector.judge import StubJudge
from detector.detect import DETECTORS
from eval.harness import eval_mode
from routing.routing import intent_action_confusion
from cluster.groupby import group
from reports.rank import rank
from reports.render import render_markdown

def main(n: int = 1000, seed: int = 0, out_dir: str = "reports/out", judge=None) -> dict:
    judge = judge or StubJudge()
    ds = generate_dataset(n=n, seed=seed)
    pairs = []
    for t in ds:
        rt = redact(t)
        for det in DETECTORS.values():
            d = det.detect(rt, judge)
            if d:
                pairs.append((d, t))
                break
    groups = group(pairs)
    ranked = rank(groups)
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, "report.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(ranked, groups))
    evaluation = {m: eval_mode(m, ds, judge) for m in ("phantom_action", "ungrounded", "misrouting")}
    print("PHANTOM:", evaluation["phantom_action"]["counts"], evaluation["phantom_action"]["rates"])
    print("INTENT→ACTION:", intent_action_confusion(ds))
    return {"report_path": report_path, "eval": evaluation, "n_patterns": len(ranked)}

if __name__ == "__main__":
    main()
