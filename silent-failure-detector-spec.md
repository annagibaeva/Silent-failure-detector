# Silent-Failure Detector — Project Spec

**One-liner:** A silent-failure detector that mines fintech support-agent traces to catch the
failures dashboards miss — phantom refunds, masked dispute errors, ungrounded policy answers — and
clusters them into the top recurring patterns a Decagon PM should fix first.

**Portfolio target:** Decagon (AI customer-support agents). Proves observability thinking,
failure-mode analysis, and — above all — **evaluation mindset**.

**Scope (weekend):** 2 detectors built flawlessly (phantom-action + ungrounded-answer), a credible
eval with hard negatives, illustrative clustering, and a PM-facing report + case study.

---

## 0. Why eval is the whole game (read this first)

The detector is easy. **A credible eval is the hard part**, and it's what separates "ML toy" from
"PM thinking." The central risk is **circularity**: I write both the failure injector and the
detector, so a naive setup just reverse-engineers my own templates and reports a meaningless 0.95 F1.
Everything below is designed to defeat that. Eval is not a downstream step here — it is the spine the
rest of the project hangs on.

### 0.1 The four eval safeguards (non-negotiable)

| # | Risk | Safeguard |
|---|------|-----------|
| 1 | **Circularity** | Failure phrasing is LLM-generated with wide paraphrase variety; a **held-out phrasing set** is never seen during detector dev; plus ~15 **hand-written transfer traces** I did not generate programmatically. |
| 2 | **Fake precision** | Dataset is **realistically imbalanced (~80% clean)** and seeds **hard negatives** — conversations that look like failures but are fine. |
| 3 | **Unstable clustering** | Cluster on a structured **failure signature**, not prose. Scale synthetic traces to ~800–1000 (free) OR frame clustering as illustrative. Don't oversell reproducibility on small n. |
| 4 | **Undefined ranking** | Explicit **severity rubric** so `freq × severity` is reproducible, not hand-waved. |

### 0.2 Metrics (the headline deliverable)

- **Per-failure-mode P / R / F1** + **confusion matrix** (never a single blended number).
- **Report on the clean class too** — false-positive rate is what a PM actually trusts/distrusts.
- **Ablation table:** heuristics-only vs. heuristics + LLM judge. This *demonstrates the tradeoff*
  and is the single most portfolio-valuable artifact in `/eval`.
- **Transfer result:** P/R/F1 on the hand-written traces (proves it isn't circular).
- **Clustering quality:** Adjusted Rand Index / homogeneity vs. injected mode labels (if claiming
  reproducibility) — else label clustering "illustrative."
- **Eval-the-evaluator:** measure the LLM judge's own agreement with ground truth; acknowledge the
  judge has an error rate and can hallucinate failures (ironic, and worth naming).

### 0.3 Regression trace set

Freeze a labeled set; re-run on every detector change to catch **my own** regressions.
Meta-narrative: the tool that catches agent regressions is itself regression-tested.

---

## 1. Domain & the PM case study

Decagon agents resolve fintech support via **tools** (lookup txn, file dispute, issue refund, freeze
card, get balance) and **RAG** (policy/help-center docs). A **silent failure** = conversation looks
successful (fluent answer, ticket "resolved," no thumbs-down) but a latent failure occurred:

- **Phantom action** — "Your dispute has been filed" when `file_dispute` returned `success:false`.
- **Error masking** — tool 500 → "Your refund is processed."
- **Ungrounded/stale** — quotes a 60-day dispute window when policy is now 90.

Fintech is chosen for **compliance-grade severity**: "we told 200 customers their dispute was filed
and it wasn't" is a regulatory incident, not a CSAT dip. That severity *is* the argument for the
project.

**Case study narrative (the README hook):** Monday, dashboard green (88% deflection, CSAT 4.3), 40k
weekend conversations. A Friday backend deploy changed `file_dispute`'s response shape; the agent now
silently fails to file disputes but confirms them anyway. ~200 customers, zero thumbs-down. The
detector clusters the 200 phantom-dispute traces into one pattern, ranks it #1 by `freq × severity`,
and hands the PM the signature, 3 examples, a root-cause hypothesis, and a mitigation.

---

## 2. Data — synthetic generator (`/generator`)

This is built **first**; all labels and therefore all metrics come from here.

### 2.1 Tool surface

| Tool | Args | Injected failure |
|------|------|------------------|
| `lookup_transaction` | `txn_id` | `null` → agent fabricates "posted yesterday" |
| `file_dispute` | `txn_id, reason` | `success:false` → "dispute filed" (**phantom action**) |
| `issue_refund` | `txn_id, amount` | 500 → "refund processed" (**error masking**) |
| `freeze_card` | `card_id` | misparsed id → wrong card frozen (**hallucinated args**) |
| `get_balance` | `account_id` | timeout → stale cached number |
| `policy_search` (RAG) | query | low-score/outdated doc → **stale/ungrounded** answer |

### 2.2 Dataset composition (defeats fake precision)

- **~80% clean** conversations (happy path).
- **Hard negatives:** agent correctly says "refund processed" *and tool succeeded*; agent
  appropriately hedges or escalates. These look failure-ish but are fine.
- **~20% injected failures**, label recorded as ground truth (hidden from detector).
- Failure **phrasing generated with paraphrase variety**; a slice of phrasings **held out**.
- Target ~800–1000 traces total (cheap, enables stable clustering).

### 2.3 Trace schema (the `/parser` contract)

```json
{
  "conversation_id": "c_001",
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
  "resolved": true, "csat": null
}
```

Note `status:"ok"` but `result.success:false` — the call worked, the *business outcome* failed. The
detector earns its keep by reading `result`, not `status`.

---

## 3. Detector — hybrid (`/features` + `/detector`)

- **Heuristics (cheap, high-precision pre-filter → features, not verdicts):** `result.success==false`,
  `result==null`, retrieval `max_score < threshold`, `latency > timeout`, repeated user message.
- **LLM judge (the judgment calls):** given final response + tool results + retrieved chunks, answer
  (1) *Does the response claim an outcome the tool results don't support?* (phantom / masking)
  (2) *Is every factual claim grounded in a retrieved chunk?* (ungrounded / stale).
  Returns `{failure_mode, confidence, evidence_span}`.
- **Weekend cut:** build **phantom-action + ungrounded** deeply. Error-masking and hallucinated-args
  are stretch. Two flawless detectors > four shallow ones.

---

## 4. Clustering (`/cluster`) — illustrative unless n is scaled

- Embed a **structured failure signature**: `(failure_mode, tool_name, error_type,
  response_claim_snippet)` — NOT raw prose (raw text clusters by topic, not failure pattern).
- HDBSCAN/k-means → recurring patterns. Report ARI vs. injected labels if claiming reproducibility;
  otherwise label "illustrative."

---

## 5. Report (`/reports`) — promote to first-class output

The PM-facing report is the **differentiator** (sells observability + evaluation thinking), so it is
not an afterthought. For each surfaced pattern:

- Rank by **`freq × severity`** using the rubric below.
- Attach signature, 3 example traces, **root-cause hypothesis**, and a **concrete mitigation in
  Decagon's language** — e.g. *"Guardrail: don't confirm a dispute unless `file_dispute` returns a
  `dispute_id`."* (AOP / guardrail framing = the actual PM deliverable.)

### Severity rubric (makes ranking reproducible)

| Failure mode | Severity |
|---|---|
| Phantom financial action (dispute/refund) | Critical (5) |
| Error masking | High (4) |
| Stale / ungrounded policy answer | Medium (3) |
| Clarification loop | Low (1) |

---

## 6. Positioning (one line in README)

Existing trace-eval tools (Arize Phoenix, LangSmith, Braintrust) score **individual** traces on
generic metrics. This mines for recurring **systemic** failure patterns tied to a specific tool +
root cause — the **prioritization view a PM needs**, ending in a concrete guardrail change.

---

## 7. Repo structure

```
/generator   synthetic trace builder w/ injectable failures + hard negatives + paraphrase variety
/parser      schema + normalizer + validators
/features    heuristic signal extractors
/detector    LLM-judge classifiers (phantom_action, ungrounded)
/cluster     embed failure signatures -> clusters
/reports     ranked freq x severity report (markdown/HTML)
/eval        ** metrics, confusion matrix, ablation, transfer set, regression set **
/docs        case study + tradeoffs narrative
README.md
```

---

## 8. Build order (always demoable; eval-first within each step)

1. `/generator` + `/parser` — imbalanced set, hard negatives, paraphrase variety, held-out phrasings,
   ground-truth labels. **Nothing can be evaluated without this.**
2. Phantom-action detector (heuristic + LLM judge).
3. **`/eval` for that one detector** — P/R/F1 + confusion matrix + hard-negative FPs **before** adding
   more. Get a real number first.
4. Ungrounded-answer detector + its eval.
5. Ablation table (heuristics-only vs. hybrid) + transfer-set result.
6. `/cluster` + `/reports` (ranked top patterns).
7. Case study: run it, screenshot the report, write the phantom-dispute story + the guardrail you'd
   ship.

---

## 9. Tradeoffs to write up (the "learnings" section)

- LLM-judge cost/latency vs. heuristic precision (and how you'd sample/tier at 40k-trace scale).
- Precision vs. recall — bias toward **precision** because false alarms destroy PM trust.
- Synthetic vs. real-trace distribution gap — named explicitly, partially addressed by the
  hand-written transfer set.
- The judge is itself an LLM that can hallucinate failures — eval-the-evaluator and own the irony.
