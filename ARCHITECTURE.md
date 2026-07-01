# Architecture

Two views: the **maturity arc** (how the product grows) and the **v1 pipeline** (what gets built first).
Diagrams are Mermaid — GitHub renders them inline.

---

## 1. Maturity arc — detector → monitor → guardrail

The same spine matures from an offline tool into an agent, then into an inline guardrail. Each version
names the *new problem* it must solve.

```mermaid
flowchart LR
    subgraph V1["v1 · Detector — offline, retrospective"]
        direction TB
        A1["Batch of traces"] --> A2["Ranked report<br/>+ one guardrail before/after"]
    end
    subgraph V2["v2 · Monitor — continuous"]
        direction TB
        B1["Post-deploy stream"] --> B2["Alerts on new / spiking<br/>failure clusters"]
    end
    subgraph V3["v3 · Guardrail — inline"]
        direction TB
        C1["Response path"] --> C2["Block · rewrite · handoff<br/>before the reply ships"]
    end
    V1 -->|"+ state · triggers · sampling &amp; cost at scale"| V2
    V2 -->|"+ latency budget · false-block rate · shadow→enforce"| V3
```

---

## 2. v1 pipeline — the buildable data flow

A stdlib-only pipeline. Detectors sit behind a common registry and a swappable **Judge seam**
(`StubJudge` for key-free CI, `ClaudeJudge` for the published numbers). Ground truth flows *only* from
the generator into `/eval` — detectors never see it.

```mermaid
flowchart TB
    G["<b>/generator</b><br/>synthetic traces + injected_labels<br/>2 verticals · hard negatives · held-out slice"]
    P["<b>/parser</b><br/>schema · validate · <b>PII redact</b> (once)"]
    F["<b>/features</b><br/>cheap heuristic signals"]

    subgraph DET["/detector — registry"]
        direction TB
        J{{"Judge seam<br/>StubJudge · ClaudeJudge"}}
        D1["PhantomDetector"]
        D2["UngroundedDetector"]
        D3["RoutingDetector"]
    end

    GB["<b>/cluster</b><br/>group-by signature_id"]
    RK["<b>/reports</b><br/>rank freq × severity (+ cost overlay)"]
    RP["report.md<br/>signature · 3 examples · root cause · guardrail"]
    GR["<b>/guardrails</b><br/>structural trigger → handoff<br/>before / after"]

    G --> P --> F --> DET
    J -.->|verdict + calibrated confidence| D1
    J -.-> D2
    J -.-> D3
    DET -->|"grounded verdicts + severity"| GB --> RK --> RP
    DET --> GR

    subgraph EVAL["/eval — the spine"]
        M["P/R/F1 · confusion · κ<br/>hard-neg FP · ablation · transfer · calibration"]
    end
    G -. "injected_labels (ground truth)" .-> M
    DET -. predictions .-> M

    classDef spine fill:#eef,stroke:#88a,stroke-width:1px;
    class EVAL,M spine;
```

**Reading it:**
- **Redact once** at the parser boundary — the judge only ever sees `<txn_id>`-style placeholders.
- **Evidence grounding:** a verdict whose `evidence_span` isn't a verbatim substring of the (redacted) trace is rejected — the verifier verifies itself.
- **Group-by, not clustering:** patterns are grouped by a stable structural `signature_id`, not an ML clustering claim.
- **`/eval` is the spine:** every version keeps it; published numbers come from the `ClaudeJudge` run on the held-out slice, never the stub.

---

## 3. Module responsibilities

| Module | Job | Key contract |
|---|---|---|
| `/generator` | Build labeled, imbalanced synthetic traces (2 verticals) | Emits ground-truth `injected_labels`; hidden from detectors |
| `/parser` | Schema + validators + **PII redaction** | `status` vs `result.success`; `intent_true` vs `intent_routed` |
| `/features` | Cheap heuristic signals | Features, not verdicts |
| `/detector` | Judge-based detectors behind a registry | `Detection{mode, severity, confidence, evidence_span}` |
| `/routing` | Intent→action mismatch | Routing confusion matrix |
| `/cluster` | Group-by structural signature | Stable `signature_id` |
| `/reports` | Rank + render | `freq × severity` (+ optional cost overlay) |
| `/guardrails` | One implemented guardrail + before/after | Detection → mitigation → measured lift |
| `/eval` | **The spine** | P/R/F1 · confusion · κ · hard-neg FP · ablation · transfer · calibration |
