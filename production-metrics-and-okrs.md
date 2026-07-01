# Production-Grade Metrics & OKRs — Silent-Failure Detector

**Companion to** `silent-failure-detector-spec-v3.md`. Defines what to monitor to run this as a
production-grade agent, across the **v1 detector → v2 monitor → v3 guardrail** maturity ladder, held to
a **conjoined bar** (detection-quality AND operational-health together — no single number can be green
while another is red).

**Decisions baked in (2026-07-01 interview):**
- Metrics span **all three versions** as a maturity ladder; each metric notes when it activates.
- **Both layers** matter and are enforced jointly (conjoined), not traded off.
- Ground truth on real traffic = **stratified human audit sample + downstream proxies** (proxies give
  the continuous signal; the audit calibrates them and provides defensible P/R with CIs).
- Data reality **TBD** → targets are stated on the synthetic + transfer set now, framed as the
  instrumentation plan to re-baseline on the first audit sample when real traffic exists.
- Precision/recall trade off **by severity**: **recall-first on Critical** (never miss a phantom
  financial action; precision managed by human triage), **precision-first on Low** (don't spam).

**Measurement hygiene (non-negotiable, per eval-rigor standard):**
- Always report **counts alongside rates** (TP/FP/FN, not just %).
- Report **Wilson confidence intervals**; flag any cell with **n < ~200** as low-confidence.
- **Per-failure-mode and per-severity** breakdowns; never a single blended F1.
- To measure **recall**, audit **unflagged** traffic too — stratified across flagged + unflagged,
  oversampling high-severity intents. Precision-only auditing is structurally blind to misses.

---

## 1. The metric tree

### North Star Metric (single, customer-centric)

**Silent-Failure Escape Rate (SFER), severity-weighted** — of all *true* silent failures in the
period, the share that reached the customer **uncaught** (missed by the detector, or in v3 not
blocked), weighted by severity so a missed Critical counts far more than a missed Low.

- **Why NSM:** it measures the core promise (is the customer protected?), it's a leading indicator of
  trust / churn / regulatory risk, and it's countable from the audit sample (with a CI).
- **Estimated from** the stratified audit sample; reported with a confidence interval.
- **Cannot be gamed alone** — driving SFER→0 by flagging everything is caught by the false-alarm and
  cost health metrics below. That tension *is* the conjoined bar.

### Input metrics (leading — move these to move the NSM)

| Metric | Definition | Direction |
|---|---|---|
| **Recall by severity** | TP / (TP+FN), per mode & severity | ↑ (Critical: hard floor) |
| **Containment/prevention rate** (v3) | true failures blocked/rewritten before reaching the customer / all true failures | ↑ |
| **Time-to-Detect (TTD)** (v2) | regression introduced → first alert | ↓ |

### Health / balancing metrics (the conjoined guardrails — keep the NSM honest)

| Metric | Definition | Direction |
|---|---|---|
| **Precision by severity** | TP / (TP+FP), per mode | ↑ (Low: hard floor) |
| **False-alarm rate** | FP / clean traces; also **alerts per 1k traces** | ↓ |
| **Judge–human agreement** | Cohen's κ (or % agreement) between LLM judge and audit labels | ↑ (κ ≥ 0.7) |
| **Coverage** | % of eligible production traffic actually evaluated | ↑ |
| **Judge cost per 1k traces** | $ spend / 1k; and % traces escalated to the judge | ↓ |
| **False-block rate** (v3) | correct responses blocked / all correct responses | ↓ (hard ceiling) |
| **Response-path latency added** (v3) | p50/p95/p99 ms overhead of the inline verifier | ↓ (hard SLO) |

### Operational reliability (is the agent itself up?)

| Metric | Definition | Version |
|---|---|---|
| **Pipeline uptime / run success** | % successful scheduled runs; failed-batch rate | v2+ |
| **Processing lag / freshness** | trace ingested → verdict available | v2+ |
| **Duplicate-alert rate** | repeat alerts for an already-surfaced pattern | v2+ |
| **Label latency** | trace → labeled ground truth (audit turnaround) | v1+ |
| **Proxy-to-audit calibration** | correlation of downstream proxies vs. audited true failures | v2+ |

### Outcome metrics (lagging — validate the leading indicators actually pay off)

Prevented customer-harm events (count, severity-weighted) · repeat-contact/reopen rate on flagged
intents · regulatory-exposure events avoided (fintech) · MTTR for a silent regression (detect→fix).

### Downstream proxies (continuous signal between audits)

Reopened/re-contacted tickets on a "resolved" intent · chargebacks/refund reversals · repeat contacts
within N days · manual escalations after an agent "confirmation." Proxies are **noisy and lagging** —
they *flag* candidate misses continuously; the **audit** turns them into calibrated truth.

---

## 2. Which metrics activate at each version (the maturity ladder)

| Metric group | v1 detector (offline) | v2 monitor (continuous) | v3 guardrail (inline) |
|---|---|---|---|
| Detection quality (P/R by severity, false-alarm, F1) | ✅ on synthetic + transfer | ✅ on real traffic (audit) | ✅ |
| Judge–human agreement (κ) | ✅ vs. injected labels | ✅ vs. audit | ✅ |
| NSM: SFER (severity-weighted) | estimated on synthetic/audit | ✅ live | ✅ live |
| Regression set as merge gate | ✅ | ✅ | ✅ |
| Coverage / sampling efficiency | — | ✅ | ✅ |
| Cost per 1k / % escalated to judge | per-run | ✅ at scale | ✅ |
| Time-to-Detect (regression drills) | — | ✅ headline | ✅ |
| Alert hygiene (precision, dedup, fatigue) | — | ✅ | — |
| Pipeline uptime / freshness | — | ✅ | ✅ |
| Response-path latency (p95/p99) | — | — | ✅ hard SLO |
| False-block rate | — | — | ✅ hard ceiling |
| Containment / prevention rate | — | — | ✅ |
| Shadow→enforce safety gate | — | — | ✅ |

---

## 3. The conjoined production bar

Ship/keep-shipping only when **all** hold simultaneously (illustrative targets — ambitious, ~60–70%
confidence; **re-baseline on the first audit sample**; report counts + Wilson CIs):

- **Critical modes (recall-first):** recall ≥ **95%** (miss almost nothing) AND precision ≥ **~65%**
  (acceptable because a human triages every Critical alert).
- **Low-severity modes (precision-first):** precision ≥ **90%** AND false-alarm ≤ **~1–2%** / alerts
  per 1k under the fatigue ceiling.
- **Trust:** judge–human agreement **κ ≥ 0.70**.
- **Coverage & cost:** ≥ **90%** of eligible traffic evaluated AND judge cost ≤ **$X / 1k** (calibrate).
- **v2 add:** injected post-deploy regression detected within **TTD ≤ 1 hour** (or ≤ N traces).
- **v3 add:** p95 added latency ≤ **~300 ms** AND false-block rate ≤ **~0.5%**, proven via **≥ 2 weeks
  shadow** under the false-block ceiling before enforce.

No clause may be waved through because another looks good. This is the WISMO-style conjoined win
condition applied to production.

---

## 4. Three OKR sets

Three credible, distinct strategic emphases. All ladder to the NSM (lower severity-weighted SFER) and
respect the conjoined bar. Targets are ambitious (60–70% confidence) and flagged where they assume data
that may not exist yet.

### OKR Set A — *Trustworthy detection* (detection-quality-led)

**Objective:** Make a detector a PM acts on without second-guessing — sensitive where it must be, quiet
where it must be.

**Key Results:**
- **KR1** — Severity-split quality holds jointly: **Critical recall ≥ 95%** (counts reported) AND
  **Low-severity precision ≥ 90%**, on the transfer + first audit sample.
- **KR2** — **False-alarm rate ≤ 2%** on clean traffic (alerts per 1k under the fatigue ceiling), on
  seeded hard negatives + audit.
- **KR3** — **Judge–human agreement κ ≥ 0.70**, measured on a stratified audit of flagged **and**
  unflagged traces.

**Rationale:** trust is the gate for everything downstream; a detector the PM distrusts is dead on
arrival. *Assumes an audit sample exists (or synthetic+transfer as the interim proxy).*

### OKR Set B — *Production reliability at scale* (operational-health-led)

**Objective:** Run continuously over the full traffic stream — cheap, fresh, and fast to catch a
regression — without a human babysitting it.

**Key Results:**
- **KR1** — **Coverage ≥ 90%** of eligible traffic evaluated at **≤ $X / 1k** judge cost (tiered:
  heuristics pre-filter all; judge only the suspicious slice).
- **KR2** — **Time-to-Detect ≤ 1 hour** for an injected post-deploy regression, validated by monthly
  regression drills; **duplicate-alert rate ≤ 10%**.
- **KR3** — **Pipeline run-success ≥ 99%** and **freshness ≤ 15 min** (ingest → verdict).

**Rationale:** a monitor that only sees a sample, lags, or flaps is a blind spot dressed as coverage.
This is the version that makes it genuinely "an agent in production." *Assumes real/replayed traffic.*

### OKR Set C — *Close the loop: prevent harm, not just observe it* (outcome/guardrail-led)

**Objective:** Move from detecting customer harm to preventing it — block the phantom confirmation
before the customer ever sees it, safely.

**Key Results:**
- **KR1** — **Severity-weighted SFER ↓ 50%** vs. the detection-only baseline (containment/prevention
  rate is the driver), via the inline guardrail.
- **KR2** — Do it safely: **false-block rate ≤ 0.5%** AND **p95 added latency ≤ 300 ms**, after **≥ 2
  weeks shadow** under the false-block ceiling before enforce.
- **KR3** — **MTTR for a silent regression ≤ 1 business day** (detect → guardrail shipped), with a
  measured before/after drop in phantom-confirmation rate on the affected slice.

**Rationale:** detection without prevention reads as observability; prevention is the product. KR2 keeps
"prevent" from becoming its own harm (blocking correct answers). *Assumes v3 build + response-path
integration.*

---

## 5. Assumptions & flags

- **Data availability is the gating assumption.** Every real-traffic target (audit κ, live SFER,
  coverage, TTD) presumes traffic + an audit budget. Until then: measure on synthetic + held-out +
  transfer, and label production numbers as estimates.
- **Audit budget scales with volume.** Stratified sampling (oversample high-severity, sample unflagged)
  keeps labeling tractable while still estimating recall — but it's a real cost line, not free.
- **Proxies lag and are noisy.** Never report a proxy as ground truth; report it as a leading candidate
  signal calibrated against the audit.
- **All targets are placeholders to calibrate.** State them as ranges, re-baseline on first real data,
  and never quote a rate without its n and CI.
