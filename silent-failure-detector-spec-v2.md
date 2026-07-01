# Silent-Failure Detector — Project Spec (v2)

**One-liner:** A silent-failure detector that mines fintech support-agent traces to catch the
failures dashboards miss — misrouted intents, phantom refunds, masked dispute errors, ungrounded
policy answers — clusters them into the top recurring patterns, and hands a PM the guardrail to ship
first.

**Portfolio target:** Decagon / Sierra (enterprise CX agents). Aimed at **Agentic PM** roles — the
artifact has to read as *product judgment applied to a real reliability problem*, not an ML toy.

**Scope (weekend):** an intent-labeled synthetic dataset with hard negatives, 2 deep detectors
(phantom-action + ungrounded-answer) plus 1 lightweight routing-mismatch check, a credible eval, an
illustrative cluster + ranked PM report, and a before/after guardrail demo.

---

## 0. What this proves — the four competencies (read this first)

This project is deliberately structured so each deliverable demonstrates one of four PM/agent
competencies. If a feature doesn't ladder to one of these, it's cut.

| Competency | Where it shows up in the build | The artifact that proves it |
|---|---|---|
| **Intent routing** | Every synthetic conversation carries a true `intent`; the agent routes intent → tool path; a routing-mismatch detector catches "customer wanted X, agent did Y" | Intent→action confusion matrix; a misrouting cluster in the report |
| **Guardrails** | Each failure mode maps to a concrete output guardrail; one is implemented and re-run to measure lift | `/guardrails` specs + a **before/after** eval table showing phantom-confirmation rate dropping |
| **Eval datasets** | Imbalanced (~80% clean), hard negatives, held-out phrasings, hand-written transfer set, frozen regression set | `/eval` metrics: per-mode P/R/F1, confusion matrix, ablation, transfer result |
| **Customer-centric design** | Severity ranked by *customer harm*, not log severity; behavioral-friction signals; precision-first because false alarms erode trust; cost/exposure framing | Severity rubric + `freq × severity × cost` ranking; the case-study narrative |

The README leads with this table. A hiring manager should see, in ten seconds, that the project is a
vehicle for these four skills.

---

## 1. Why eval is the whole game

The detector is easy. **A credible eval is the hard part**, and it's what separates "ML toy" from
"PM thinking." The central risk is **circularity**: I write both the failure injector and the
detector, so a naive setup just reverse-engineers my own templates and reports a meaningless 0.95 F1.
Everything below is designed to defeat that. Eval is the spine the rest of the project hangs on — it
is also the clearest demonstration of the **eval-datasets** competency.

### 1.1 The four eval safeguards (non-negotiable)

| # | Risk | Safeguard |
|---|------|-----------|
| 1 | **Circularity** | Failure phrasing is LLM-generated with wide paraphrase variety; a **held-out phrasing set** is never seen during detector dev; plus ~15 **hand-written transfer traces** I did not generate programmatically. |
| 2 | **Fake precision** | Dataset is **realistically imbalanced (~80% clean)** and seeds **hard negatives** — conversations that look like failures but are fine. |
| 3 | **Unstable clustering** | Cluster on a structured **failure signature**, not prose. Scale to ~800–1000 traces (free) OR frame clustering as illustrative. Don't oversell reproducibility on small n. |
| 4 | **Undefined ranking** | Explicit **severity rubric** so `freq × severity × cost` is reproducible, not hand-waved. |

### 1.2 Metrics (the headline deliverable)

- **Per-failure-mode P / R / F1** + **confusion matrix** (never a single blended number).
- **Report on the clean class too** — false-positive rate is what a PM actually trusts/distrusts.
- **Intent-routing confusion matrix** — true intent vs. routed action; misrouting recall.
- **Ablation table:** heuristics-only vs. heuristics + LLM judge. Demonstrates the cost/precision
  tradeoff; the single most portfolio-valuable artifact in `/eval`.
- **Guardrail before/after:** phantom-confirmation rate on the same set with the guardrail off vs. on.
- **Transfer result:** P/R/F1 on the hand-written traces (proves it isn't circular).
- **Eval-the-evaluator:** measure the LLM judge's own agreement with ground truth; name that the
  judge can itself hallucinate failures and own the irony.

### 1.3 Regression trace set

Freeze a labeled set; re-run on every detector change to catch **my own** regressions. Meta-narrative:
the tool that catches agent regressions is itself regression-tested.

---

## 2. Domain & the PM case study

Decagon/Sierra agents resolve fintech support via **intent routing** → **tools** (lookup txn, file
dispute, issue refund, freeze card, get balance) and **RAG** (policy/help-center docs). A **silent
failure** = the conversation looks successful (fluent answer, ticket "resolved," no thumbs-down) but a
latent failure occurred:

- **Misrouted intent** — customer asks to *dispute* a charge; agent routes to *refund lookup* and
  answers confidently about the wrong thing.
- **Phantom action** — "Your dispute has been filed" when `file_dispute` returned `success:false`.
- **Error masking** — tool 500 → "Your refund is processed."
- **Ungrounded / stale** — quotes a 60-day dispute window when policy is now 90.

Fintech is chosen for **compliance-grade severity**: "we told 200 customers their dispute was filed
and it wasn't" is a regulatory incident, not a CSAT dip. That severity *is* the argument for the
project, and it's why ranking is **customer-centric** rather than log-centric.

**Case-study narrative (the README hook):** Monday, dashboard green — 88% deflection, CSAT 4.3, 40k
weekend conversations. A Friday backend deploy changed `file_dispute`'s response shape; the agent now
silently fails to file disputes but confirms them anyway. ~200 customers, zero thumbs-down. The
detector clusters the 200 phantom-dispute traces into one pattern, ranks it #1 by `freq × severity ×
cost`, and hands the PM the signature, 3 examples, a root-cause hypothesis, and **the guardrail to
ship**.

---

## 3. Data — synthetic generator (`/generator`)

Built **first**; all labels and therefore all metrics come from here.

### 3.1 Intent + tool surface

Every conversation is generated from a true `intent`, which the simulated agent routes to a tool
path. Routing can itself be injected as wrong (misrouting), independent of whether the tool succeeds.

| Intent | Correct tool path | Args | Injected failure modes |
|---|---|---|---|
| dispute_charge | `file_dispute` | `txn_id, reason` | `success:false` → "dispute filed" (**phantom action**); routed to refund instead (**misrouting**) |
| request_refund | `issue_refund` | `txn_id, amount` | 500 → "refund processed" (**error masking**) |
| check_balance | `get_balance` | `account_id` | timeout → stale cached number |
| lost_card | `freeze_card` | `card_id` | misparsed id → wrong card frozen (**hallucinated args**) |
| policy_question | `policy_search` (RAG) | query | low-score/outdated doc → **stale/ungrounded** answer |

### 3.2 Dataset composition (defeats fake precision)

- **~80% clean** conversations (happy path), correctly routed and correctly answered.
- **Hard negatives:** agent says "refund processed" *and the tool succeeded*; agent appropriately
  hedges or escalates; agent re-confirms intent before acting. These look failure-ish but are fine.
- **~20% injected failures**, label recorded as ground truth (hidden from detector).
- Failure **phrasing generated with paraphrase variety**; a slice of phrasings **held out**.
- Target ~800–1000 traces (cheap, enables stable clustering).

### 3.3 Trace schema (the `/parser` contract)

```json
{
  "conversation_id": "c_001",
  "intent_true": "dispute_charge",
  "intent_routed": "dispute_charge",
  "injected_labels": ["phantom_action"],
  "turns": [
    {"role": "user", "text": "I want to dispute a $50 charge"},
    {"role": "agent", "text": "Sure, what's the transaction?", "tool_calls": []},
    {"role": "user", "text": "txn_8842"},
    {"role": "agent", "text": "Your dispute has been filed, you'll hear back in 5 days.",
     "tool_calls": [
       {"name": "file_dispute", "args": {"txn_id": "txn_8842", "reason": "unauthorized"},
        "result": {"success": false, "error": "txn_not_found"}, "status": "ok", "latency_ms": 220}
     ]}
  ],
  "behavioral_signals": {"user_reask": false, "user_correction": false, "abandoned": false},
  "resolved": true, "csat": null
}
```

Two things the detector earns its keep on: `status:"ok"` but `result.success:false` (the call worked,
the *business outcome* failed), and `intent_true ≠ intent_routed` (the customer was answered
confidently about the wrong thing).

> **Customer-centric note on `behavioral_signals`:** user re-asks, corrections ("no, I meant…"), and
> abandonment are the purest silent-failure signal *on real traffic*. In synthetic data I author them,
> so they risk becoming another reverse-engineered template (the circularity in §1.1). Rule: include
> them as features, but report their lift **only on the hand-written transfer set**, and name the
> synthetic-vs-real gap explicitly. A feature that doubles as an eval-maturity signal.

---

## 4. Intent routing layer (`/routing`)

A lightweight check, not a third deep detector — enough to showcase the competency without blowing the
weekend.

- The generator labels `intent_true`; the simulated agent produces `intent_routed`.
- **Routing-mismatch detector (heuristic + small LLM check):** flag conversations where the tool path
  taken doesn't serve the stated intent, *especially* when the final answer is confident.
- **Eval:** intent→action confusion matrix; recall on injected misroutings; false-positive rate on
  correctly-routed hard negatives (e.g. a legitimate intent change mid-conversation must NOT flag).
- **PM framing:** misrouting is the *upstream* failure — a customer routed to the wrong path can never
  be served correctly downstream, so it ranks high on customer harm even when frequency is low.

---

## 5. Detector — hybrid (`/features` + `/detector`)

- **Heuristics (cheap, high-precision pre-filter → features, not verdicts):** `result.success==false`,
  `result==null`, retrieval `max_score < threshold`, `latency > timeout`, repeated user message,
  intent/tool mismatch.
- **LLM judge (the judgment calls):** given final response + tool results + retrieved chunks, answer
  (1) *Does the response claim an outcome the tool results don't support?* (phantom / masking)
  (2) *Is every factual claim grounded in a retrieved chunk?* (ungrounded / stale).
  Returns `{failure_mode, confidence, evidence_span}`.
- **Weekend cut:** build **phantom-action + ungrounded** deeply, plus the **routing-mismatch**
  heuristic. Error-masking and hallucinated-args are stretch. Two flawless detectors + one routing
  check > four shallow ones.

---

## 6. Guardrails (`/guardrails`) — promoted to a first-class deliverable

Detection without "now what" reads junior. Each failure mode maps to a concrete **output guardrail** —
a rule the agent should enforce before it speaks. This is the actual PM deliverable and the
**guardrails** competency.

| Failure mode | Guardrail (in Decagon/Sierra language) |
|---|---|
| Phantom action (dispute) | Don't confirm a dispute unless `file_dispute` returns a `dispute_id`. |
| Error masking (refund) | Don't claim "processed" on any non-2xx tool result; surface a handoff. |
| Ungrounded / stale | Don't state a policy figure without a retrieved chunk above score τ; cite it. |
| Misrouting | Re-confirm intent before any state-changing tool call when routing confidence < τ. |

**Implement one end-to-end** (the phantom-action guardrail), re-generate the affected slice with the
guardrail enforced, and produce a **before/after table**: phantom-confirmation rate, and the new
"correctly handed off" rate. This is the demo money shot and proves you close the loop from detection →
mitigation → measured improvement.

---

## 7. Clustering (`/cluster`) — illustrative unless n is scaled

- Embed a **structured failure signature**: `(failure_mode, intent_true, tool_name, error_type,
  response_claim_snippet)` — NOT raw prose (raw text clusters by topic, not failure pattern).
- HDBSCAN/k-means → recurring patterns. Report ARI / homogeneity vs. injected labels if claiming
  reproducibility; otherwise label "illustrative."

---

## 8. Report (`/reports`) — the differentiator

The PM-facing report sells observability + evaluation thinking, so it is a first-class output. For
each surfaced pattern:

- Rank by **`freq × severity × cost`** using the rubric below.
- Attach signature, 3 example traces, **root-cause hypothesis**, and the **guardrail to ship** (from
  §6).
- One **annotated trace** per top cluster: the failure moment highlighted (the swallowed
  `success:false` next to the confident "dispute filed").

### Severity rubric (makes ranking reproducible) + cost dimension

| Failure mode | Severity | Customer-cost proxy |
|---|---|---|
| Phantom financial action (dispute/refund) | Critical (5) | regulatory-exposure events × est. remediation cost |
| Error masking | High (4) | failed transactions × handoff cost |
| Misrouted intent | High (4) | unserved customers × repeat-contact cost |
| Stale / ungrounded policy answer | Medium (3) | misinformed customers × complaint rate |
| Clarification loop | Low (1) | added handle time |

The cost column is what turns a clustering output into a number a support-ops leader budgets against —
the **customer-centric** competency made quantitative.

---

## 9. Positioning (one line in README)

Existing trace-eval tools (Arize Phoenix, LangSmith, Braintrust) score **individual** traces on
generic metrics. This mines for recurring **systemic** failure patterns tied to a specific intent +
tool + root cause — the **prioritization view a PM needs**, ending in a concrete guardrail change.

---

## 10. Repo structure

```
/generator   synthetic trace builder: intents, injectable failures, hard negatives, paraphrase variety
/parser      schema + normalizer + validators
/routing     intent->action mismatch checks + routing eval
/features    heuristic signal extractors (incl. behavioral signals)
/detector    LLM-judge classifiers (phantom_action, ungrounded)
/guardrails  guardrail specs + one implemented guardrail + before/after harness
/cluster     embed failure signatures -> clusters
/reports     ranked freq x severity x cost report (markdown/HTML) w/ annotated traces
/eval        ** metrics, confusion matrix, ablation, transfer set, regression set **
/docs        case study + tradeoffs narrative + the four-competency README
README.md
```

---

## 11. Tradeoffs to write up (the "learnings" section)

- LLM-judge cost/latency vs. heuristic precision (and how you'd sample/tier at 40k-trace scale).
- Precision vs. recall — bias toward **precision** because false alarms destroy PM trust.
- Synthetic vs. real-trace distribution gap — named explicitly, partially addressed by the
  hand-written transfer set; behavioral signals reported transfer-only for the same reason.
- Intent routing as upstream root cause — why a low-frequency misrouting can still rank above a
  high-frequency clarification loop once customer harm is priced in.
- The judge is itself an LLM that can hallucinate failures — eval-the-evaluator and own the irony.
