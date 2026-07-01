# Silent-Failure Detector — Product Plan & Roadmap (v3, consolidated)

**Status:** Canonical top-level plan as of 2026-07-01. Supersedes `silent-failure-detector-spec-v2.md`
for **positioning, market/customers, scope, and roadmap**. The detailed eval design and severity
rubric in v2 remain the reference for those specifics — this doc does not restate them line by line.

**One-liner:** A silent-failure detection & remediation layer for enterprise CX agents. It mines
support-agent traces for the *successful-looking* failures — where the conversation looks resolved but
a latent tool or RAG failure occurred: misrouted intents, phantom actions, masked tool errors,
ungrounded policy answers — ranks them by customer harm, root-causes each to a specific tool, and hands
over the guardrail to ship. It grows from an offline **detector** (v1) into a continuous **monitor**
(v2) into an inline **guardrail** (v3).

**Intended use:** A reusable agent and framework for enterprise CX-agent reliability. The taxonomy,
synthetic generator, detector, eval harness, and guardrail loop are vendor- and vertical-agnostic — a
new domain or platform is a config swap, not a rebuild. The artifact must read as *product judgment
applied to a real reliability problem*, not an ML toy; eval credibility is the centerpiece.

---

## 0. What changed in this revision

Decisions made in the 2026-07-01 planning session, recorded so the plan reflects real choices:

1. **Product form = a maturity arc, not one thing.** v1 detector → v2 monitor → v3 guardrail. This
   resolves the "is it a tool or an agent?" tension: it starts as a tool and becomes an agent.
2. **Complementary residual-failure layer (point 1).** It sits *on top of* a best-in-class agent
   platform, turning the failures that still slip through into a ranked, root-caused backlog — a
   complement to the platform, not a competitor to it.
3. **Vertical-pluggable, fintech-flagship (point 3).** Fintech stays the flagship for compliance-grade
   severity; one **subscription** example (Notion-style: canceled-but-still-billed) proves generality.
4. **Clustering demoted to a group-by (point 4).** On ~800–1000 traces, HDBSCAN/ARI is oversell.
   Reframe honestly as a group-by over a structured failure signature. The ranked *report* is the
   deliverable; grouping is just how it's assembled.
5. **Name the detection ceiling (point 5).** A "what this cannot catch yet" section is a first-class
   part of the eval story — see §5.
6. **v3 is a verifier-not-solver guardrail in the response path (point 6).** This is a well-understood
   pattern that de-risks v3. It is kept **architecturally**, but this repo is **not coupled** to any
   other project — the pattern is reused here as a design choice, not a code dependency.
7. **No external agent-trace benchmark.** Explicitly excluded from every version. The
   synthetic-vs-real gap is mitigated by the hand-written transfer set and by naming the gap openly,
   not by an external benchmark.

**Refinements folded in (later 2026-07-01 pass):**

8. **Calibrated confidence + per-severity thresholds (impr. 1).** The judge emits a confidence that is
   *calibrated*; operating thresholds are selected **per severity** to deliver recall-first on Critical
   and precision-first on Low. This is the mechanism behind the severity-dependent P/R decision — see
   §6.1.
9. **Grounding the judge's own output (impr. 2).** A verdict's `evidence_span` must be a **verbatim
   substring** of the response or a tool result; ungrounded verdicts are rejected — the verifier
   verifies itself. See §6.2.
10. **Cost is a configurable overlay, not an invented number (impr. 3).** Default ranking is
    `freq × severity`; the **customer-set cost multiplier** is an optional overlay, so the ranking is
    never a fabricated dollar figure.
11. **Circularity-defense protocol is specified, not asserted (impr. 4).** Concrete rules for phrasing
    generation, the held-out slice, and the hand-written transfer set — see §6.3.
12. **Data governance & PII is in scope (impr. 5).** PII is redacted before the judge; retention and
    residency are addressed — see §9.

---

## 1. Positioning

**Category.** Agent reliability & observability — specifically, silent-failure *detection and
remediation* for enterprise CX agents.

**Positioning statement.**
> For the product and support-ops owners running enterprise CX agents, this is the layer that surfaces
> the *successful-looking* failures that otherwise go unseen — a fluent answer and a "resolved" ticket
> over a latent tool or RAG failure — ranked by customer harm, root-caused to a specific tool, and
> handed over as the guardrail to ship. Unlike generic trace-eval tools (Arize Phoenix, LangSmith,
> Braintrust) that score *individual* traces on *generic* metrics, it mines recurring *systemic*
> patterns and closes the loop to a measured fix.

**Two edges** (what it dials up while others dial down):
- **Systemic pattern-mining** — failures tied to a specific *intent + tool + root cause*, not a flood
  of per-trace scores.
- **The PM prioritization view** — ranked by `freq × severity` with a customer-configurable **cost**
  overlay, ending in a concrete guardrail, not a metric.

**Relationship to the platform.** A mature agent platform already ships analytics and QA. This is not a
competitor to that; it is the residual-risk layer that turns a platform's remaining silent failures
into a ranked, root-caused, guardrail-ready backlog. The pitch is always complementary.

---

## 2. Market & customers

### 2.1 Segments — by job-to-be-done

Illustrated with representative enterprise CX deployments so each segment is concrete, independent of
any single platform.

| Segment | Who (representative) | Job-to-be-done | When they reach for it |
|---|---|---|---|
| **Agent PM / product owner** | PM owning the support agent at a subscription SaaS | "Tell me which systemic failure to fix first, with evidence and a fix." | Retrospective audit; reliability-backlog prioritization |
| **Support-Ops / CX quality & observability owner** | Support-ops lead at a marketplace or media-subscription company | "Alert me to new silent-failure patterns after a deploy — before a customer or regulator does." | Post-deploy; regression watch |
| **Platform FDE / deployment engineer** | A forward-deployed engineer standing up an agent for a fintech client | "Prove the agent is reliable to my customer, and configure guardrails that hold." | During/after a customer deployment |

**Buyer vs. beneficiary nuance to articulate:** the *user* is the FDE/PM and the enterprise's ops
owner; the *beneficiary* is the enterprise (avoided exposure) and the end customer (not being falsely
told a money problem is solved).

### 2.2 Vertical-pluggable, fintech-flagship

Same taxonomy, swapped domain — the "prove generality" move. Ship the flagship plus **one**
subscription example.

| Vertical | Illustrative example | Flagship silent failure | Severity |
|---|---|---|---|
| **Fintech / payments** *(flagship)* | a BNPL / payments provider | "Your dispute has been filed" while `file_dispute` returned `success:false` | Critical — regulatory |
| **Subscription / SaaS** | a productivity SaaS (Notion-style) | "Your subscription is canceled" while `cancel_subscription` failed — customer keeps getting billed | High |

The subscription case is deliberately relatable: a canceled-but-still-billed failure is a trust and
refund-liability event, not a CSAT dip — the same *shape* of harm as the fintech flagship, in a
non-regulated domain, which is what proves the taxonomy generalizes.

### 2.3 Value delivered (in customer language)

- **Enterprise:** avoided regulatory/remediation exposure; fewer repeat contacts (misrouting is the
  *upstream* failure); protected trust; faster root-cause on a silent regression (an MTTR for the
  failures the dashboard never flags).
- **Platform (the agent vendor):** a reliability/guardrail differentiator, a churn-risk reducer, an
  FDE-efficiency multiplier.
- **End customer:** not quietly told a money problem is solved when it isn't.

---

## 3. Product roadmap — detector → monitor → guardrail

Each version names what it does, who uses it, its scope, the *new* problems it must solve, and its
definition of done. `/eval` is the spine and is present in every version.

### v1 — The Detector *(offline, retrospective, human-in-the-loop — the weekend build)*

- **Does:** a batch of traces → a ranked report of the top silent-failure patterns; each pattern has a
  signature, 3 examples, a root-cause hypothesis, and the guardrail to ship. Plus **one** guardrail
  implemented end-to-end with a **before/after** table.
- **User:** Agent PM / FDE running a reliability audit.
- **Scope:** 2 deep detectors (**phantom-action** + **ungrounded-answer**) + a lightweight
  **routing-mismatch** check; a **vertical-pluggable generator** (fintech flagship + the Notion
  subscription example); **group-by** report (not "clustering").
- **New problems:** defeat eval circularity (imbalanced set, hard negatives, held-out phrasings,
  hand-written transfer set); make ranking reproducible (severity rubric); **calibrate the judge's
  confidence and pick a per-severity operating threshold** (§6.1); **reject verdicts whose evidence
  span doesn't ground** (§6.2).
- **Done when:** honest per-mode P/R/F1 + confusion matrix, the hard-negative false-positive rate, the
  transfer-set result, and one measured guardrail loop. **This is the credibility core — never cut.**

### v2 — The Monitor *(continuous — this is where it becomes an "agent")*

- **Does:** ingests new traces on a **schedule / post-deploy trigger**, holds a **baseline of known
  clusters**, and detects **new or spiking** patterns — then acts (alert to Slack / open a ticket)
  with the ranked pattern + root cause.
- **User:** Support-Ops / observability owner.
- **New problems** (the substance of v2):
  - **Alert dedup & fatigue** — surface a *new* pattern once, not the same one every run.
  - **Drift** — distinguish a real regression from normal variation.
  - **The cost story** — sampling/tiering so the LLM judge runs economically at 40k+ traces:
    heuristics pre-filter cheaply; the judge only reads the suspicious slice. Report cost-per-1k.
  - **Regression set as a merge gate** — the tool that catches agent regressions is itself
    regression-tested.
- **Done when:** it detects an injected post-deploy regression within N traces, at a reported alert
  precision and cost-per-1k.

### v3 — The Guardrail *(inline — detect → prevent)*

- **Does:** the highest-value guardrails run as **verifiers in the response path** — block, rewrite, or
  hand off *before* the agent confirms a phantom action. Verifier-not-solver: it checks the proposed
  response against tool results and retrieved chunks; it does not generate the answer.
- **User:** FDE / platform deploying guardrails for a customer.
- **New problems** (the substance of v3):
  - **Latency budget** — a verifier in the response path must be fast.
  - **False-block rate** — blocking a *correct* answer is its own customer harm; this is the v3
    analogue of v1's false-positive rate and must be measured, not assumed away.
  - **Handoff UX** — what the customer sees when a claim is blocked.
  - **Shadow → enforce rollout** — run in shadow mode and measure before gating live traffic.
- **Done when:** phantom-confirmation rate drops at an acceptable false-block rate and latency, proven
  via a shadow-then-enforce rollout.

> *Note (de-risking v3):* the verifier-in-the-response-path pattern is well understood and has been
> built independently before — so v3 is lower-risk than it looks. The pattern is reused here as a
> design choice, not a code dependency; this repo stays standalone.

---

## 4. Architecture — the shared spine, versioned

```
Ingest ─▶ Parser/schema ─▶ Heuristic features ─▶ LLM-judge detectors ─▶ Structured signature
(gen v1 /    (status:ok vs      (cheap, high-        (phantom, ungrounded,     │
 stream v2+)  result.success)    precision filter)    routing-mismatch)        ▼
                                                        Group-by + freq×severity (+cost) rank
                                                                                │
        ┌───────────────────────────────────────────────────────┬─────────────┘
        ▼ (v1)                        ▼ (v2)                      ▼ (v3)
   Ranked PM report            Post-deploy monitor           Inline guardrail
   + guardrail recs            + new-cluster alerts           (verifier in response path)
   + 1 before/after loop       + drift/dedup + sampling       block / rewrite / handoff
```

**Component boundaries** (each has one job, a clear interface, and independent testability):

| Unit | Job | Key contract |
|---|---|---|
| `/generator` | Build imbalanced, labeled synthetic traces per vertical | Emits ground-truth `injected_labels`; hidden from the detector |
| `/parser` | Schema + normalizer + validators | Exposes `status` vs. `result.success`; `intent_true` vs. `intent_routed` |
| `/features` | Cheap, high-precision heuristic signals | Features, **not** verdicts |
| `/detector` | LLM-judge classifiers | Returns `{failure_mode, confidence, evidence_span}`; `confidence` calibrated (§6.1); `evidence_span` verified as a verbatim substring, ungrounded verdicts rejected (§6.2) |
| `/routing` | Intent→action mismatch check | Routing confusion matrix; FP on legit mid-conversation intent change |
| `/cluster` | **Group-by** structured signature | `(failure_mode, intent_true, tool, error_type, claim_snippet)` |
| `/reports` | Rank by `freq × severity` (+ optional customer-set cost overlay) | Signature + 3 examples + root cause + guardrail + annotated trace |
| `/guardrails` | Guardrail specs + one implemented + before/after harness | The detection→mitigation→measurement loop |
| `/eval` | **The spine** | Per-mode P/R/F1, confusion matrix, hard-negative FP, ablation, transfer set, regression set |

Versioning adds, it doesn't rewrite: v2 swaps `/generator` input for a streaming ingest + a
baseline/alert store; v3 wraps `/detector` + `/guardrails` as an inline verifier with a
latency budget and a shadow/enforce switch.

---

## 5. Detection ceiling — what this cannot catch yet (point 5)

Stated openly, because naming the ceiling is the eval-honesty signal:

- **Strong** where the tool `result` *contradicts* the claim — phantom action, error masking,
  ungrounded-against-retrieved. The detector earns its keep reading `result`, not `status`.
- **Weak** where the tool returned `success:true` but the outcome is *semantically wrong* —
  **hallucinated args** (froze the *wrong* card; disputed the *wrong* txn). The trace looks clean;
  catching it needs argument-vs-intent reasoning, which is a v2+ direction.
- **Out of scope** where there is no tool signal at all and the claim is a pure world-knowledge
  hallucination unrelated to any retrieved chunk — a different problem than silent *tool/RAG* failure.

This ceiling is a feature of the writeup, not a gap to hide.

---

## 6. Eval — the spine (reference)

Unchanged in principle from spec-v2 §1; the headline deliverables:

- Per-failure-mode **P / R / F1** + **confusion matrix** — never a single blended number.
- The **clean-class false-positive rate**, including on seeded hard negatives.
- **Intent-routing confusion matrix** — true intent vs. routed action; misrouting recall.
- **Ablation table** — heuristics-only vs. heuristics + LLM judge (the highest-signal artifact; shows
  the cost/precision tradeoff).
- **Guardrail before/after** — phantom-confirmation rate off vs. on.
- **Transfer result** — P/R/F1 on the ~15 hand-written traces; the primary defense against circularity
  now that no external benchmark is used.
- **Eval-the-evaluator** — the LLM judge's own agreement with ground truth; the judge can itself
  hallucinate failures, and that irony is named.
- **Report counts alongside rates**, with confidence caveats at small n.

### 6.1 Confidence calibration & per-severity thresholds (impr. 1)

The severity-dependent P/R decision (recall-first on Critical, precision-first on Low) is only real if
there is a knob to turn. The judge emits a `confidence`; we **calibrate** it (reliability diagram /
isotonic or Platt scaling on the eval set) so the score means what it says, then **select an operating
threshold per severity**:

- **Critical modes** (phantom financial action): low threshold → **recall-first**; borderline verdicts
  are surfaced and a human triages them.
- **Low-severity modes** (clarification loop): high threshold → **precision-first**; only high-confidence
  verdicts fire, so the report doesn't spam.

Report the **calibration curve** and the chosen thresholds alongside the metrics — the thresholds are
part of the deliverable, not a hidden constant.

### 6.2 Grounding the judge's own output (impr. 2)

The judge returns an `evidence_span`. Before a verdict is accepted, the span must be a **verbatim
substring** of the final response or a tool result; a verdict whose evidence doesn't ground is
**rejected** (counted as a judge abstention, not a detection). This makes the verifier verify itself —
it cannot report a failure it can't point at — and it directly strengthens the eval-the-evaluator story
(the judge's *own* hallucinations are caught mechanically, not just measured).

### 6.3 Circularity-defense protocol (impr. 4)

The circularity defense is specified, not asserted:

- **Phrasing generation** uses a **different prompt (and where possible a different model)** than the
  judge, so the detector isn't reading its own author's wording.
- **Held-out phrasing slice** = **distinct templates frozen before detector development** and never seen
  during it; used only at final eval.
- **Hand-written transfer set** (~15 traces) is authored **by hand without looking at the generator
  templates** — the primary defense now that no external benchmark is used.
- The **regression set** is frozen and re-run on every detector/prompt/model change to catch the
  author's own regressions.

---

## 7. Scope guardrails (v1 cut-line)

Drop from the bottom if behind; **never** cut the top three protections.

**Cut order:** behavioral-feature ablation → ARI/reproducibility claim (relabel "illustrative") →
routing as an LLM check (keep heuristic-only) → annotated-trace screenshots (plain text).

**Never cut:** the hard-negative FP rate · the transfer-set result · the one guardrail before/after.
A reviewer who trusts the eval forgives a thin feature set; one who catches an inflated F1 discounts
everything.

---

## 8. Open risks & tradeoffs (the learnings section)

- **Synthetic vs. real distribution gap** — the largest unmitigated risk now that no external benchmark
  is used. Addressed only by the hand-written transfer set and by naming the gap. A real design-partner
  trace set is the eventual v2 upgrade path.
- **LLM-judge cost/latency vs. heuristic precision** — and how sampling/tiering handles 40k-trace scale
  (the substance of v2).
- **Precision vs. recall** — biased *by severity* (recall-first on Critical, precision-first on Low),
  delivered via calibrated per-severity thresholds (§6.1); false alarms destroy PM trust on low-severity
  modes faster than misses.
- **Intent routing as upstream root cause** — why a low-frequency misrouting can still rank above a
  high-frequency clarification loop once customer harm is priced in.
- **The judge is itself an LLM that can hallucinate failures** — eval-the-evaluator, and own the irony.

---

## 9. Data governance & PII (impr. 5)

The tool processes support traces that contain PII (transaction and account ids, card numbers, names,
addresses) — and it argues *from* compliance severity, so omitting data governance would be
self-contradicting. In scope from v1:

- **Redact before the judge.** PII is masked/tokenized in the `/parser` stage before any trace reaches
  the LLM judge; the judge sees placeholders (`<txn_id>`, `<account_id>`), not raw values. Detection
  logic keys off structure (`status` vs. `result.success`, `intent_true` vs. `intent_routed`), not the
  PII itself, so redaction costs no recall.
- **Retention & minimization.** Store only what the report needs — the structured signature and short
  redacted snippets, not full raw traces — with a defined retention window.
- **Residency & processor terms.** Named as a deployment requirement: where traces are processed, and
  under what data-processing terms the LLM judge runs. A blocker to state, not solve, at v1.

This is a v1 design constraint (redaction in the parser), with residency/retention policy as a v2
deployment concern.
