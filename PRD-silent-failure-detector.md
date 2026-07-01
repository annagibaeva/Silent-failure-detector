# PRD — Silent-Failure Detector

> Aligned to `silent-failure-detector-spec-v3.md` (canonical plan, 2026-07-01). This PRD is the
> requirements view; the v3 spec is the source of truth for positioning, scope, and roadmap.

## 1. Summary

A **silent-failure detection & remediation layer** for enterprise CX agents. It reads the conversation
logs (traces) of AI support agents and finds the failures that look like successes — cases where the
agent told a customer "your dispute is filed" when it actually wasn't. It groups these hidden failures
into recurring patterns, ranks them by customer harm, root-causes each to a specific tool, and hands
the owner the guardrail to ship first.

It is a **reusable agent and framework**: the taxonomy, synthetic generator, detector, eval harness,
and guardrail loop are vendor- and vertical-agnostic — a new domain or platform is a config swap, not a
rebuild. It matures along an arc: an offline **detector** (v1) → a continuous **monitor** (v2) → an
inline **guardrail** (v3). Its center of gravity is **evaluation credibility**, not just detection.

---

## 2. Stakeholders & personas

| Role | In the product | Notes |
|------|----------------|-------|
| Product owner | Author / maintainer | Owns the design and the eval discipline end to end. |
| Agent PM / product owner | Primary user | "Tell me which systemic failure to fix first, with evidence and a fix." |
| Support-Ops / CX quality & observability owner | Primary user | "Alert me to new silent-failure patterns after a deploy — before a customer or regulator does." |
| Platform FDE / deployment engineer | Primary user | "Prove the agent is reliable to my customer, and configure guardrails that hold." |
| LLM judge (Claude) | Automated evaluator inside the tool | Makes the hard judgment calls; its own error rate is measured, not assumed away. |

---

## 3. Background

**What this is about.** Enterprises run AI agents that answer customer-support questions and take real
actions — filing disputes, issuing refunds, freezing cards, canceling subscriptions, looking up
balances. Most of the time these agents work. But sometimes they fail *silently*: the answer sounds
fluent, the ticket is marked "resolved," the customer doesn't complain, and yet something real went
wrong underneath.

**Why now.** As these agents take more real, high-stakes actions, a silent failure stops being a
quality dip and becomes a compliance incident. "We told 200 customers their dispute was filed and it
wasn't" is a regulatory problem, not a CSAT problem. Generic trace-eval and analytics score individual
traces on generic metrics; they underserve the *systemic, ranked, root-caused* view. This is the
residual-failure layer that sits **on top of** a best-in-class agent platform — a complement to it, not
a competitor.

**Why it's possible now.** Two things changed. First, agent traces (full logs of every tool call and
its result) are now standard, so the raw evidence exists. Second, LLM judges are now good and cheap
enough to read a conversation and ask "does this answer match what the tools actually returned?" — the
judgment call that used to need a human.

---

## 4. Objective & Key Results

**Objective.** Catch the silent failures that look like successes, group them into the top recurring
patterns, and rank those patterns by customer harm so an owner knows exactly what to fix first — ending
in a concrete guardrail, not just a metric.

**Why eval is the whole game.** Building a detector is easy. Proving it works *without fooling yourself*
is the hard part. Because the same person writes both the failure injector and the detector, a naive
setup just reverse-engineers its own templates and reports a meaningless 0.95 F1. Defeating that
circularity is the spine of the project.

**Key Results (SMART).**

- **KR1 — Honest accuracy.** Per-failure-mode Precision / Recall / F1 plus a confusion matrix for the
  two core detectors (phantom-action, ungrounded-answer). No single blended number, ever. Report counts
  alongside rates, with confidence caveats at small n.
- **KR2 — Trust (low false alarms).** Report the false-positive rate on the clean class explicitly,
  including on seeded hard negatives. Bias by severity: precision-first on low-severity modes.
- **KR3 — Proof it isn't circular.** Report P/R/F1 on ~15 hand-written transfer traces and on a
  held-out phrasing set the detector never saw during development.
- **KR4 — The tradeoff is visible.** Ship an ablation table: heuristics-only vs. heuristics + LLM judge.
  The highest-signal artifact in `/eval`.
- **KR5 — Prioritization works.** Produce a ranked report of the top recurring patterns by
  `freq × severity` (with an optional customer-set **cost** overlay) using a fixed severity rubric, each
  with a signature, 3 examples, a root-cause hypothesis, and a concrete guardrail.
- **KR6 — Eval-the-evaluator.** Measure the LLM judge's own agreement with ground truth and name its
  error rate openly.

---

## 5. Market segments

Defined by the *job to be done*, illustrated with representative enterprise CX deployments so each
segment is concrete, independent of any single platform.

- **The PM who must prioritize fixes** — has analytics but no *systemic* view. Job: "tell me which
  systemic failure to fix first, with evidence."
- **The quality / observability owner** — needs to catch regressions before a regulator or a customer
  does. Job: "alert me to new silent-failure patterns after a deploy."
- **The platform FDE / deployment engineer** — proving reliability to a customer and configuring
  guardrails during a deployment.

**Vertical-pluggable, fintech-flagship.** Same taxonomy, swapped domain:

| Vertical | Illustrative example | Flagship silent failure | Severity |
|---|---|---|---|
| **Fintech / payments** *(flagship)* | a BNPL / payments provider | "Your dispute has been filed" while `file_dispute` returned `success:false` | Critical — regulatory |
| **Subscription / SaaS** | a productivity SaaS (Notion-style) | "Your subscription is canceled" while `cancel_subscription` failed — customer keeps getting billed | High |

**Constraints.**
- The v1 build is deliberately narrow: two detectors done flawlessly, not four done shallowly.
- All v1 data is synthetic, which creates a real-vs-synthetic distribution gap that must be named, not
  hidden.
- Cost and latency of the LLM judge matter at scale (40k+ traces), so the design must show how it would
  sample or tier — even if the v1 demo runs on ~800–1000 traces.

---

## 6. Value proposition

**The job customers hire this for:** "Show me the failures my analytics can't surface as *patterns*,
grouped and ranked by customer harm, so I know what to fix first — and prove the tool itself is
trustworthy."

**What customers gain.**
- A prioritized list of *systemic* failure patterns, not a flood of individual trace scores.
- For each pattern: a clear signature, real examples, a root-cause hypothesis, and a concrete guardrail
  written in their own language (e.g. "don't confirm a dispute unless `file_dispute` returns a
  `dispute_id`").
- Honest, per-mode metrics they can trust, including how often the tool cries wolf.

**Pains avoided.**
- The "looks resolved, customer harmed" blind spot.
- Drowning in per-trace alerts with no prioritization.
- Being handed a "0.95 F1" they can't believe because the eval was circular.

**Where it wins (the value curve).** Generic trace-eval tools (Arize Phoenix, LangSmith, Braintrust)
score *individual* traces on *generic* metrics. This dials those down and dials up two things they
underserve: **systemic pattern-mining** (failure tied to a specific intent + tool + root cause) and
**the prioritization view an owner needs**, ending in a guardrail change.

---

## 7. Solution

### 7.1 UX / flow

The primary "interface" is a generated owner-facing report (markdown/HTML), treated as a first-class
output.

```
Ingest ─▶ Parser/schema ─▶ Heuristic features ─▶ LLM-judge detectors ─▶ Structured signature
(gen v1 /    (status:ok vs      (cheap, high-        (phantom, ungrounded,     │
 stream v2+)  result.success)    precision filter)    routing-mismatch)        ▼
                                                        Group-by + freq×severity (+cost) rank
                                                                                │
        ┌───────────────────────────────────────────────────────┬─────────────┘
        ▼ (v1)                        ▼ (v2)                      ▼ (v3)
   Ranked report               Post-deploy monitor           Inline guardrail
   + guardrail recs            + new-cluster alerts           (verifier in response path)
   + 1 before/after loop       + drift/dedup + sampling       block / rewrite / handoff
```

**The case-study narrative:** Monday, dashboard green — 88% deflection, CSAT 4.3, 40k weekend
conversations. A Friday backend deploy quietly changed `file_dispute`'s response shape; the agent now
fails to file disputes but confirms them anyway. ~200 customers affected, zero thumbs-down. The tool
groups the 200 phantom-dispute traces into one pattern, ranks it #1, and hands the owner the signature,
3 examples, a root-cause hypothesis, and the guardrail to ship.

### 7.2 Key features

1. **Synthetic generator** (`/generator`) — realistic, imbalanced traces (~80% clean) with injected,
   ground-truth-labeled failures, seeded hard negatives, wide paraphrase variety, and a held-out
   phrasing slice. Vertical-pluggable. Built first; every metric depends on it.
2. **Parser** (`/parser`) — a strict trace schema, normalizer, and validators. Key insight: a tool call
   can be `status:"ok"` while `result.success:false` — the call worked, the *business outcome* failed.
   Also exposes `intent_true` vs. `intent_routed`.
3. **Heuristic features** (`/features`) — cheap, high-precision signals used as inputs, not verdicts:
   `result.success==false`, `result==null`, retrieval `max_score < τ`, latency over timeout, repeated
   user messages, intent/tool mismatch.
4. **LLM-judge detectors** (`/detector`) — the two core classifiers: **phantom action / error masking**
   (does the response claim an outcome the tool results don't support?) and **ungrounded / stale** (is
   every factual claim grounded in a retrieved chunk?). Each returns
   `{failure_mode, confidence, evidence_span}`, with the confidence **calibrated** and a **per-severity
   operating threshold** (recall-first on Critical, precision-first on Low), and the `evidence_span`
   **verified as a verbatim substring** of the response or a tool result — ungrounded verdicts are
   rejected (the verifier verifies itself).
5. **Routing-mismatch check** (`/routing`) — a lightweight heuristic + small LLM check for
   `intent_true`-serving tool path vs. the path taken; misrouting is the *upstream* root cause.
6. **Grouping** (`/cluster`) — a **group-by over a structured failure signature**
   `(failure_mode, intent_true, tool_name, error_type, response_claim_snippet)` — not raw prose, and
   framed honestly as a group-by, not an ML clustering claim.
7. **Ranked report** (`/reports`) — top patterns by `freq × severity` (+ optional customer-set cost
   overlay), each with signature, 3 examples, root-cause hypothesis, a concrete guardrail, and one
   annotated trace.
8. **Guardrails** (`/guardrails`) — each failure mode maps to a concrete output guardrail; one is
   implemented end-to-end with a before/after table (detection → mitigation → measured improvement).
9. **Eval suite** (`/eval`) — the headline: per-mode P/R/F1, confusion matrix, clean-class FP rate,
   ablation table, transfer-set result, eval-the-evaluator, and a frozen regression set re-run on every
   detector change. Plus a **confidence-calibration curve with the chosen per-severity thresholds**, an
   **evidence-grounding check on the judge's own verdicts**, and a **specified circularity-defense
   protocol**: phrasings generated by a different prompt/model than the judge; held-out templates frozen
   before detector dev; the hand-written transfer set authored without the generator templates.

**Severity rubric (makes ranking reproducible):**

| Failure mode | Severity | Customer-cost proxy (configurable) |
|---|---|---|
| Phantom financial action (dispute/refund) | Critical (5) | regulatory-exposure events × est. remediation cost |
| Error masking | High (4) | failed transactions × handoff cost |
| Misrouted intent | High (4) | unserved customers × repeat-contact cost |
| Stale / ungrounded policy answer | Medium (3) | misinformed customers × complaint rate |
| Clarification loop | Low (1) | added handle time |

Cost is a **customer-configurable overlay** — the ops leader supplies the $ per remediation. The default
ranking is `freq × severity`, so no dollar figure is invented and the ranking stays defensible.

### 7.3 Detection ceiling — what it cannot catch yet

Stated openly, because naming the ceiling is the eval-honesty signal:

- **Strong** where the tool `result` *contradicts* the claim — phantom action, error masking,
  ungrounded-against-retrieved. The detector earns its keep reading `result`, not `status`.
- **Weak** where the tool returned `success:true` but the outcome is *semantically wrong* —
  hallucinated args (froze the *wrong* card; disputed the *wrong* txn). A v2+ direction.
- **Out of scope** where there is no tool signal and the claim is a pure world-knowledge hallucination
  unrelated to any retrieved chunk — a different problem than silent *tool/RAG* failure.

### 7.4 Technology notes

- Hybrid detection: cheap heuristics as a pre-filter feeding an LLM judge for the judgment calls.
- Grouping via a structured-signature group-by (not an oversold clustering claim on small n).
- Fintech chosen as the flagship for compliance-grade severity — that severity *is* the argument for
  the project — but the taxonomy is vertical-agnostic.

### 7.5 Assumptions (believed, not yet proven)

- Synthetic traces with wide paraphrase variety + a hand-written transfer set are a good-enough proxy
  for real agent traces. **Largest unmitigated risk; named explicitly, only partially addressed.**
- A structured failure signature groups into meaningful patterns better than raw prose.
- An LLM judge can reliably distinguish "claimed outcome" from "actual tool result." **The judge can
  itself hallucinate failures — measured via eval-the-evaluator, and the irony is owned, not hidden.**
- Biasing precision vs. recall *by severity* (recall-first on Critical, precision-first on Low) is the
  right call.

### 7.6 Data governance & PII

Support traces carry PII (transaction/account ids, card numbers, names, addresses), and the project
argues *from* compliance severity — so governance is in scope, not an afterthought.

- **Redact before the judge.** PII is masked/tokenized in `/parser` before any trace reaches the LLM
  judge (the judge sees `<txn_id>` / `<account_id>` placeholders). Detection keys off structure
  (`status` vs. `result.success`, `intent_true` vs. `intent_routed`), not PII, so redaction costs no
  recall.
- **Retention & minimization.** Store only redacted signatures and short snippets, not full raw traces,
  with a defined retention window.
- **Residency & processor terms.** Where traces are processed and under what data-processing terms the
  LLM judge runs — a named deployment requirement.

A v1 design constraint (redaction in the parser); residency/retention policy is a v2 deployment concern.

---

## 8. Release — the maturity arc

The v1 build stays demoable at every step, eval-first within each step.

### v1 — The Detector *(offline, retrospective — the first build)*
Two detectors built flawlessly (phantom-action + ungrounded-answer) plus a routing-mismatch check; a
vertical-pluggable generator (fintech flagship + the subscription example); a credible eval with hard
negatives and a transfer set; a group-by report; and one guardrail implemented with a before/after
table. **Build order:** generator + parser → phantom-action detector → its eval (get one honest number
first) → ungrounded detector + eval → routing check → ablation + transfer set → one guardrail loop →
group-by + ranked report → case study.

### v2 — The Monitor *(continuous — becomes an "agent")*
Adds state (a baseline of known clusters), a trigger (scheduled / post-deploy), and an action (alert).
Detects new or spiking clusters. New problems: alert dedup/fatigue, drift, and the cost story
(sampling/tiering the judge economically at 40k+ traces). Regression set becomes a merge gate. A real
design-partner trace set is the credibility upgrade path.

### v3 — The Guardrail *(inline — detect → prevent)*
The top guardrails run as verifiers in the response path — block / rewrite / hand off before the agent
confirms a phantom action. New problems: latency budget, false-block rate (blocking a *correct* answer
is its own harm), handoff UX, and a shadow → enforce rollout.

---

## 9. Learnings / tradeoffs to write up

- LLM-judge cost/latency vs. heuristic precision — and how you'd sample/tier at 40k-trace scale.
- Precision vs. recall — biased *by severity*, not uniformly.
- The synthetic-vs-real distribution gap — the largest unmitigated risk; named explicitly, partially
  addressed by the hand-written transfer set.
- Intent routing as upstream root cause — why a low-frequency misrouting can rank above a high-frequency
  clarification loop once customer harm is priced in.
- The judge is itself an LLM that can hallucinate failures — eval-the-evaluator, and own the irony.
