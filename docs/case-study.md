# v1 Case Study — Monday Morning, Phantom Disputes

Monday morning. The dashboard is green — 88% deflection, CSAT 4.3, 40k weekend conversations. But a
Friday backend deploy quietly changed `file_dispute`'s response shape. The agent now silently fails to
file disputes — and confirms them anyway. ~200 customers were told their dispute was filed. Zero
thumbs-down. Nothing on the dashboard moved.

This case study walks through what the v1 **Silent-Failure Detector** finds on that class of incident,
how it ranks patterns, and what guardrail to ship first — using the offline pipeline on synthetic +
transfer traces.

---

## Honesty caveats (read first)

1. **Published metrics must come from `ClaudeJudge`.** Every headline P/R/F1, κ, ablation, and transfer
   number in a production writeup must be produced by `python -m eval.published` with
   `ANTHROPIC_API_KEY` set (see `.env.example`). The ranked `reports/out/report.md` from
   `python run_v1.py` uses **`StubJudge`** — a key-free CI smoke path, not a result. StubJudge is
   phantom-only by design and will not reflect real judge behavior on ungrounded or hybrid detection.

2. **Thresholds are severity-tiered, not auto-calibrated.** v1 uses fixed `threshold_for(mode)`
   constants (0.3 / 0.5 / 0.8 by severity band). The reliability diagram from `run_published` is
   *reported* but not yet *fed back* into thresholds; isotonic calibration is the v2 `[calibrate]`
   upgrade.

> **Action:** Copy `.env.example` → `.env`, set your key, run `python -m eval.published`, then paste
> the `reports/out/published.md` block below the placeholder in this doc and in the README.

---

## Dataset composition (held-out slice, seed=7, n=1000)

| Stat | Value |
|------|-------|
| Total traces | 1000 |
| Clean | 800 (80%) |
| `phantom_action` | 100 (dispute + cancel verticals) |
| `ungrounded` | 50 |
| `misrouting` | 50 |

Hard negatives are flagged with `is_hard_negative=True`, labeled clean, and tool `success:true`.

---

## Published eval (ClaudeJudge — pending)

```
# Paste from reports/out/published.md after: python -m eval.published
```

### CI smoke reference only (`StubJudge`, held-out, seed=7)

*Do not cite these as published results — they illustrate pipeline shape only.*

| Mode | counts | P/R/F1 | κ | hard_neg_fp |
|------|--------|--------|---|-------------|
| phantom_action | tp=100, fp=0, fn=0, tn=900 | 1.0 / 1.0 / 1.0 | 1.0 | 0 |
| ungrounded | tp=0, fp=0, fn=50, tn=950 | 0 / 0 / 0 | 0.0 | 0 |
| misrouting | tp=50, fp=0, fn=0, tn=950 | 1.0 / 1.0 / 1.0 | 1.0 | 0 |

StubJudge does not judge ungrounded — expect zeros until ClaudeJudge runs.

### Ablation (phantom, held-out slice)

| Row | precision | recall | F1 |
|-----|-----------|--------|-----|
| heuristics_only | 1.0 | 1.0 | 1.0 |
| hybrid (registry + judge) | 1.0 | 1.0 | 1.0 |

### Transfer set (15 hand-written traces, phantom mode)

counts: tp=4, fp=0, fn=0, tn=11 — rates: P/R/F1 = 1.0 *(StubJudge smoke; re-run under ClaudeJudge)*

---

## Top ranked patterns (`run_v1.py`, seed=0, StubJudge smoke)

Three patterns demonstrate generality across detectors and verticals:

### #1 — phantom_action (dispute_charge → file_dispute)

- **Score:** 50 × severity 5 = 250
- **Hypothesis:** `file_dispute` returned `txn_not_found` while the agent claimed success.
- **Guardrail:** Don't confirm a dispute unless `file_dispute` returns a `dispute_id`.
- **Example claim:** "…filed…"

### #2 — phantom_action (cancel_subscription → cancel_subscription)

- **Score:** 50 × severity 5 = 250
- **Hypothesis:** `cancel_subscription` returned `billing_active` while the agent claimed cancellation.
- **Guardrail:** Same family — structural confirmation gate on subscription cancel tool outcome.
- **Example claim:** "…Done…"

### #3 — misrouting (dispute_charge → issue_refund)

- **Score:** 50 × severity 4 = 200
- **Hypothesis:** Customer wanted a dispute; agent ran `issue_refund` and said "Your refund is processed."
- **Guardrail:** Re-confirm intent before any state-changing tool call when routing confidence < τ.
- **Example claim:** "…Your refund is processed.…"

---

## Intent → action confusion (seed=0, n=1000)

| intent_true | served tool | count |
|-------------|-------------|-------|
| dispute_charge | file_dispute | 287 |
| dispute_charge | **issue_refund** | **50** ← misrouting slice |
| cancel_subscription | cancel_subscription | 194 |
| policy_question | policy_search | 183 |
| check_balance | get_balance | 149 |
| request_refund | issue_refund | 137 |

The dispute→refund confusion row is the synthetic misrouting positive class.

---

## Guardrail before/after (dispute phantom slice, n=300, seed=3)

Structural trigger: rewrite agent text when `file_dispute` lacks `dispute_id`. Metric: success-claim
text (`CONFIRM_WORDS`) on the ground-truth dispute-phantom slice — non-tautological.

| Metric | Off | On |
|--------|-----|-----|
| phantom_confirmation_rate | 1.0 | **0.0** |
| handed_off_rate | — | 1.0 |
| slice_n | 15 | 15 |

---

## Detection ceiling (spec §5)

- **Strong:** tool `result` contradicts the claim (phantom, error masking, ungrounded vs retrieved).
- **Weak:** `success:true` but semantically wrong args (wrong txn, wrong card) — v2+.
- **Out of scope:** pure world-knowledge hallucination with no tool/RAG signal.

---

## Tradeoffs (spec §8)

- **Synthetic vs real gap** — largest unmitigated risk; transfer set + held-out phrasing are partial
  defenses; design-partner traces are the v2 path.
- **Judge cost/latency vs heuristics** — ablation table is the artifact; tiering at 40k traces is v2.
- **Precision vs recall by severity** — recall-first on Critical (phantom), precision-first on Low;
  v1 thresholds are fixed tiers, not yet calibrated from the reliability curve.
- **Routing as upstream root cause** — misrouting ranks high despite equal frequency to ungrounded
  because severity 4 × customer harm pricing.
- **Eval-the-evaluator** — the judge can hallucinate failures; grounding rejects ungrounded spans;
  κ and transfer set measure agreement with generator labels, not ground truth in production.
