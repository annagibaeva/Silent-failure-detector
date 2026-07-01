# eval/published.py
from __future__ import annotations
import os
from generator.generate import generate_dataset
from parser.redact import redact
from detector.detect import DETECTORS
from eval.harness import eval_mode, ablation, load_transfer
from eval.local_env import load_local_env
from eval.metrics import cohen_kappa
from detector.calibrate import reliability_bins

def collect_conf_correct(mode: str, traces, judge):
    det = DETECTORS[mode]
    confs, correct = [], []
    for t in traces:
        d = det.detect(redact(t), judge, threshold=0.0)   # threshold 0 to collect the full score range
        if d is not None:
            confs.append(d.confidence)
            correct.append(mode in t.injected_labels)
    return confs, correct

def run_published(n: int = 1000, seed: int = 7, out_dir: str = "reports/out", judge=None) -> dict:
    if judge is None:
        load_local_env()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("SKIP: set ANTHROPIC_API_KEY to produce published numbers.")
            return {"skipped": True}
        from detector.judge import ClaudeJudge
        judge = ClaudeJudge(api_key=os.environ["ANTHROPIC_API_KEY"])
    ds = generate_dataset(n=n, seed=seed, held_out=True)     # held-out phrasings: the anti-circularity slice
    per_mode = {m: eval_mode(m, ds, judge) for m in ("phantom_action", "ungrounded", "misrouting")}
    confs, correct = collect_conf_correct("phantom_action", ds, judge)
    reliability = reliability_bins(confs, correct)
    transfer = eval_mode("phantom_action", load_transfer(), judge)
    ab = ablation(ds, judge)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "published.md"), "w", encoding="utf-8") as fh:
        fh.write("# Published numbers (ClaudeJudge, held-out)\n\n")
        for m, r in per_mode.items():
            fh.write(f"## {m}\ncounts={r['counts']} rates={r['rates']} kappa={r['kappa']:.3f} "
                     f"hard_neg_fp={r['hard_negative_fp']}\n\n")
        fh.write(f"## transfer (phantom)\ncounts={transfer['counts']} rates={transfer['rates']}\n\n")
        fh.write(f"## ablation\n{ab}\n\n## reliability\n{reliability}\n")
    return {"per_mode": per_mode, "transfer": transfer, "ablation": ab, "reliability": reliability}

if __name__ == "__main__":
    run_published()
