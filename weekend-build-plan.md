# Silent-Failure Detector — Weekend Build Plan

Companion to `silent-failure-detector-spec-v2.md`. The goal is a repo that is **always demoable** and
**eval-first within every step** — get a real number before adding scope. Each block names the
competency it proves so the build never drifts from the portfolio purpose.

**Four competencies to surface:** intent routing · guardrails · eval datasets · customer-centric design.

**Guiding rule:** if you fall behind, cut from the bottom of §"Cut-line", never from the eval.

---

## Saturday — data, detection, first real number

### Block 1 · Generator + parser (~3h) — proves *eval datasets*
- Build `/generator`: intents, correct tool paths, the 5 tools from spec §3.1.
- Inject failures: phantom-action + ungrounded first (the two deep detectors), plus misrouting flag.
- Compose the set: ~80% clean, hard negatives, ~20% injected; ~800–1000 traces.
- Paraphrase variety; **hold out a phrasing slice**; reserve schema field for `behavioral_signals`.
- Build `/parser`: schema validator + normalizer. Assert every trace has ground-truth labels.
- **Demoable at end:** print dataset composition stats (class balance, mode counts, held-out size).
- **Done when:** a validator passes on 100% of generated traces and the label distribution matches target.

### Block 2 · Phantom-action detector (~2.5h) — proves *guardrails* (setup) + hybrid design
- `/features`: heuristic signals (`result.success==false`, `result==null`, latency, repeated msg).
- `/detector`: LLM judge for "response claims an outcome the tool results don't support."
- Return `{failure_mode, confidence, evidence_span}`.
- **Demoable at end:** run on 10 traces, show the evidence span it highlights.

### Block 3 · `/eval` for phantom-action ONLY (~2h) — proves *eval datasets* (the headline)
- Per-mode P/R/F1 + confusion matrix; **report the clean-class false-positive rate**.
- Run against hard negatives explicitly; a clean "refund processed + tool succeeded" must NOT flag.
- **Get one honest number before building anything else.** If precision is low, fix here — do not pile on detectors.
- **Done when:** you can state "phantom-action precision X, recall Y, FP-rate Z on hard negatives."

### Block 4 · Ungrounded-answer detector + its eval (~2.5h) — proves *eval datasets*, RAG failure
- LLM judge for "is every factual claim grounded in a retrieved chunk above score τ?"
- Same eval treatment: P/R/F1, confusion matrix, hard-negative FP rate.
- **Demoable at end:** two detectors, each with a real metric block.

> **Saturday definition of done:** an intent-labeled dataset and two detectors, each with an honest,
> hard-negative-tested metric. That alone is a credible portfolio core.

---

## Sunday — routing, guardrail loop, clustering, report, narrative

### Block 5 · Routing-mismatch check + routing eval (~1.5h) — proves *intent routing*
- `/routing`: heuristic + small LLM check for `intent_true`-serving tool path vs. taken path.
- Eval: intent→action confusion matrix; misrouting recall; FP on legitimate mid-conversation intent change.
- **PM line to capture:** misrouting is the upstream root cause — ranks on customer harm, not frequency.

### Block 6 · Ablation + transfer set (~1.5h) — proves *eval datasets* (the portfolio-defining artifact)
- Ablation table: heuristics-only vs. heuristics + LLM judge. This shows the cost/precision tradeoff.
- Run all detectors on the ~15 **hand-written transfer traces**; report P/R/F1. This defeats circularity.
- *(Stretch)* behavioral-feature lift, transfer-set only.

### Block 7 · One guardrail, end-to-end + before/after (~2h) — proves *guardrails*
- Implement the phantom-action guardrail: "don't confirm a dispute without a `dispute_id`."
- Re-generate the affected slice with the guardrail enforced.
- **Before/after table:** phantom-confirmation rate off vs. on; new "correctly handed off" rate.
- **This is the demo money shot** — detection → mitigation → measured improvement.

### Block 8 · Cluster + ranked report (~2h) — proves *customer-centric design*
- `/cluster`: embed structured failure signature `(failure_mode, intent_true, tool, error_type, claim_snippet)`.
- Report ARI vs. injected labels if claiming reproducibility; else label "illustrative."
- `/reports`: rank by `freq × severity × cost`; per cluster attach signature, 3 examples, root-cause
  hypothesis, the guardrail to ship, and one **annotated trace** with the failure moment highlighted.

### Block 9 · Case study + README (~2h) — ties it together
- Write the phantom-dispute Monday-morning story (spec §2).
- Lead the README with the **four-competency table** (spec §0).
- Tradeoffs / learnings section (spec §11): judge cost, precision bias, synthetic gap, eval-the-evaluator.
- Screenshot the report + the before/after table for the repo and any recruiter post.

> **Sunday definition of done:** routing eval, an ablation + transfer result, one measured guardrail
> loop, a ranked report, and a README that frames the whole thing around the four competencies.

---

## Proof-bundle checklist (map to the original brief)

| Bundle item | Produced by | Competency headline |
|---|---|---|
| GitHub repo: `/generator /parser /routing /features /detector /guardrails /cluster /reports /eval /docs` | All blocks | structure & rigor |
| Minimal live demo: traces → report of patterns | Blocks 8–9 | observability |
| Benchmark report + test set | Blocks 1, 3, 4, 6 | **eval datasets** |
| Intent→action confusion matrix | Block 5 | **intent routing** |
| Before/after guardrail table | Block 7 | **guardrails** |
| `freq × severity × cost` ranking + case study | Blocks 8–9 | **customer-centric design** |
| Tradeoffs / learnings writeup | Block 9 | PM maturity |

---

## Cut-line (drop from the bottom up if behind)

1. Behavioral-feature ablation (Block 6 stretch) — nice-to-have, transfer-only anyway.
2. ARI reproducibility claim → relabel clustering "illustrative" (Block 8).
3. Routing as an LLM check → keep heuristic-only (Block 5).
4. Annotated-trace screenshots → plain text examples (Block 8).

**Never cut:** the hard-negative FP rate, the transfer-set result, or the one guardrail before/after.
Those three are what make the project credible rather than impressive-looking. A reviewer who trusts
your eval will forgive a thin feature set; one who catches an inflated F1 will discount everything.

---

## Recruiter one-liner (post-build)

> Built a silent-failure detector that mines fintech support-agent traces for misrouted intents,
> phantom actions, and ungrounded answers — validated on an imbalanced, hard-negative synthetic set
> with a hand-written transfer slice, and closed the loop with a guardrail that measurably cut
> phantom-confirmations.
