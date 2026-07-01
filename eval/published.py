# eval/published.py
from __future__ import annotations
import argparse
import os
from generator.generate import generate_dataset
from parser.redact import redact
from detector.detect import DETECTORS
from eval.harness import eval_mode, ablation, load_transfer
from eval.local_env import load_local_env
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


def _judge_stats(judge) -> dict:
    if hasattr(judge, "api_calls"):
        return {"api_calls": judge.api_calls, "cache_hits": judge.cache_hits}
    return {}


def run_published(
    n: int = 1000,
    seed: int = 7,
    out_dir: str = "reports/out",
    judge=None,
    model: str | None = None,
    cache: bool = True,
    label: str = "ClaudeJudge",
) -> dict:
    if judge is None:
        load_local_env()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("SKIP: set ANTHROPIC_API_KEY to produce published numbers.")
            return {"skipped": True}
        from detector.judge import make_claude_judge
        judge = make_claude_judge(api_key=os.environ["ANTHROPIC_API_KEY"], model=model, cache=cache)
    model_name = getattr(getattr(judge, "_inner", judge), "_model", label)
    print(f"run_published: n={n} seed={seed} model={model_name} cache={cache}", flush=True)
    ds = generate_dataset(n=n, seed=seed, held_out=True)
    per_mode = {m: eval_mode(m, ds, judge) for m in ("phantom_action", "ungrounded", "misrouting")}
    confs, correct = collect_conf_correct("phantom_action", ds, judge)
    reliability = reliability_bins(confs, correct)
    transfer = eval_mode("phantom_action", load_transfer(), judge)
    ab = ablation(ds, judge)
    stats = _judge_stats(judge)
    if stats:
        print(f"judge done: {stats['api_calls']} API calls, {stats['cache_hits']} cache hits", flush=True)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "published.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"# Published numbers ({label}, held-out)\n\n")
        fh.write(f"n={n} seed={seed} model={model_name} cache={cache} {stats}\n\n")
        for m, r in per_mode.items():
            fh.write(f"## {m}\ncounts={r['counts']} rates={r['rates']} kappa={r['kappa']:.3f} "
                     f"hard_neg_fp={r['hard_negative_fp']}\n\n")
        fh.write(f"## transfer (phantom)\ncounts={transfer['counts']} rates={transfer['rates']}\n\n")
        fh.write(f"## ablation\n{ab}\n\n## reliability\n{reliability}\n")
    print(f"wrote {path}", flush=True)
    return {"per_mode": per_mode, "transfer": transfer, "ablation": ab, "reliability": reliability, **stats}


def main() -> None:
    p = argparse.ArgumentParser(description="Run ClaudeJudge published eval on held-out slice.")
    p.add_argument("-n", type=int, default=1000)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--model", default=None, help="Anthropic model id (or set JUDGE_MODEL in .env)")
    p.add_argument("--out-dir", default="reports/out")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--label", default="ClaudeJudge")
    args = p.parse_args()
    run_published(
        n=args.n,
        seed=args.seed,
        out_dir=args.out_dir,
        model=args.model,
        cache=not args.no_cache,
        label=args.label,
    )


if __name__ == "__main__":
    main()
