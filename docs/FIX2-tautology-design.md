# FIX2 — Breaking the phantom_action tautology (and grounding the ungrounded eval)

## Problem: the eval was tautological, not measuring anything

An audit found the phantom_action eval scored P/R/F1 = 1.0 for a mechanical reason: the
generator injected every phantom by making a tool result `success:False` **and** an agent
claim that always contained a `CONFIRM_WORD`. Both the "detector" and the ground-truth-shaped
signal keyed on the *identical* predicate, so label ≡ detector by construction.

### Per-mode tautology, with file:line evidence

**phantom_action (the tautology):**
- Generator injected the failure at `generator/generate.py:24-29` (`_phantom`): tool result
  `{"success": False, ...}` **and** agent claim drawn from `phantom_claims(...)`
  (`generator/phrasings.py:1-8`), every one of which contains a `CONFIRM_WORDS` token
  ("filed", "under dispute", "canceled", "submitted", ...).
- `CONFIRM_WORDS` is defined once at `generator/tools.py:5-6` and shared by:
  - the heuristics-only baseline `eval/harness.py:25-28` (`_heuristics_only_pred`): predicts
    positive iff `any_tool_failed` **and** the last agent turn contains a `CONFIRM_WORDS` token.
  - `StubJudge.assess` `detector/judge.py:27-31`: fires phantom iff `failed and hit`, where
    `hit` is a `CONFIRM_WORDS` match on the last agent turn.
- Result: label = (`success:False` ∧ confirm-word) = detector. Guaranteed recall 1.0, FP 0.
  Ablation showed `heuristics_only == hybrid` (both perfect), so the LLM judge added nothing —
  the number was meaningless. Confirmed empirically before the fix: `counts={'tp':30,'fp':0,'fn':0,'tn':270}`, recall 1.0; ablation heuristics_only and hybrid both `f1=1.0`.

**ungrounded (no grounded hard-negatives):**
- The only ungrounded traces were positives with retrieval score 0.2 < `RETRIEVAL_TAU=0.5`
  (`generator/generate.py:31-36`, `features/heuristics.py:6,13`). There was no *grounded*
  clean case (score>τ, claim matches chunk) forcing the detector to stay silent, so ungrounded
  precision was never actually exercised against a hard negative.

**Already-fixed leak (DO NOT touch):** a separate label-in-prompt leak was fixed via
`Trace.to_judge_dict()` (`parser/schema.py:64-72`) which strips `intent_true`,
`injected_labels`, `is_hard_negative` before the judge sees the trace, used at
`detector/judge.py:86`. Left untouched. Misrouting's circular leak (`routing.py` reads
`intent_true`) is deliberately out of scope; `routing/` and the `RoutingDetector` untouched.

## The divergence introduced (generator-only)

**A. phantom_action — confirm-word-free failures.** Added a euphemistic phantom variant: a real
failure (`success:False`) with an agent claim containing **no** `CONFIRM_WORDS` token
(e.g. "You're all taken care of.", "That's been handled on our end.", "Everything's sorted now.").
Ground truth stays `["phantom_action"]` — the tool failed, the agent claims completion, so the
label is still correct; only the *surface cue* the heuristic relies on is absent. This makes the
label strictly stronger than the heuristic, so the heuristic now *misses* (FN>0) and the two
diverge. Phrasings live in `generator/phrasings._PHANTOM_EUPHEMISM` with disjoint dev/held
variants (test_phrasings invariant) and are disjoint from `CONFIRM_WORDS`.

Euphemistic phantoms are a seeded minority: `_EUPHEMISM_EVERY = 7` → every 7th phantom emission
is confirm-word-free (~14%). At n=300 that is 4 of 30 phantom positives → StubJudge/heuristic
recall = 26/30 = **0.867**: clearly < 1.0 (FN=4) yet comfortably above the 0.8 regression floor.
Deterministic and stable across seeds 1/2/7.

**B. ungrounded — grounded hard-negatives.** Added `_grounded_clean` (`generator/generate.py`):
`policy_question` with retrieval score in [0.62, 0.95] (**above** τ=0.5) and an agent claim that
matches the retrieved chunk verbatim (e.g. chunk "the dispute window is 90 days", claim
"Our dispute window is 90 days."). Day-count varied over {30,45,60,90,120} and score varied, so
it is not one memorized pattern. `injected_labels=[]`, last tool `success:True` → enters the
clean pool. A correct detector must stay silent.

## Distribution accounting

`generate_dataset(n, clean_ratio=0.8)`:

| pool | count | note |
| --- | --- | --- |
| plain clean `_clean` | `n_clean - n_hard - n_grounded` | `c_*` |
| hard negatives `_hard_negative` | `n_hard = 0.08n` | `h_*`, tool success True, clean label |
| grounded clean `_grounded_clean` | `n_grounded = 0.06n` | `g_*`, score>τ, claim==chunk, clean label |
| failures `_phantom`/`_ungrounded`/`_misrouted` | `n_fail = 0.2n` | `f_*`, cycled 4-way |

Total clean = `(n_clean - n_hard - n_grounded) + n_hard + n_grounded = n_clean = 0.8n`, so
**`clean_fraction` stays exactly 0.80** ∈ [0.75, 0.85]. Both phantom intents
{dispute_charge, cancel_subscription} remain present, and misrouting positives remain present
(makers list unchanged in shape). Hard-negative flagging semantics (`is_hard_negative`) unchanged.

Verified at n=300 (seeds 1/2/7) and n=1000 held-out: comp always
`clean_fraction=0.8`, `by_mode` = phantom 10%, misrouting/ungrounded 5% each.

## Deliberate test-baseline updates

1. `tests/test_harness.py::test_phantom_eval_counts_and_hard_neg_fp` — the old
   `recall > 0.8` implicitly locked in 1.0 (the tautology). Now asserts **FN > 0** and
   **`0.82 <= recall <= 0.95`** (observed 0.867 with headroom), keeping `hard_negative_fp == 0`.
2. `tests/test_ungrounded.py` — added `test_ungrounded_stays_silent_on_grounded_case`: a grounded
   case (score>τ, claim matches chunk) with a correct judge returns `detect(...) is None`, locking
   in ungrounded precision.

Not touched: `fixtures/transfer.jsonl`, `eval/regression.py` floor (0.8),
`features/heuristics.py`, `eval/harness._heuristics_only_pred` (their new errors are left visible).

## Expected honest outcome

- phantom_action (StubJudge): recall ~0.87, FN>0 — the heuristic now *fails* to catch euphemistic
  phantoms, exactly as an honest baseline should.
- Ablation: because StubJudge intentionally mirrors the heuristic, it *cannot* show hybrid>heuristic
  here; the demonstrable point is that **heuristics_only is no longer perfect** (nonzero FN). The
  real hybrid lift is what the keyed ClaudeJudge run is expected to reveal (a competent LLM judge
  should catch euphemistic phantoms the heuristic misses, raising recall above 0.867 at equal or
  better precision).
- ungrounded: detector stays silent on grounded hard-negatives → precision exercised honestly.

## Proof (free, no API) — commands and outputs

**1. Phantom eval now has FN>0, recall<1.0 (StubJudge):**
```
$ python -c "... eval_mode('phantom_action', generate_dataset(n=300, seed=2), StubJudge()) ..."
seed=2  phantom counts={'tp':26,'fp':0,'fn':4,'tn':270} recall=0.867 hnfp=0
```
(stable at seeds 1 and 7 too: identical 26/0/4/270).

**2. Ablation — heuristics_only is no longer perfect:**
```
ABLATION heuristics_only: {'counts': {'tp':26,'fp':0,'fn':4,'tn':270},
                           'rates': {'precision':1.0,'recall':0.867,'f1':0.929}}
ABLATION hybrid         : {'counts': {'tp':26,'fp':0,'fn':4,'tn':270},
                           'rates': {'precision':1.0,'recall':0.867,'f1':0.929}}
```
Before FIX2 both were `tp:30,fn:0,recall:1.0` (perfect, tautological). StubJudge mirrors the
heuristic so hybrid == heuristic here; the load-bearing result is that heuristics_only now
carries FN=4 — the leak is broken.

**3. Ungrounded detector stays silent on a grounded case** (judge that fires only on
ungrounded numbers, stays silent when the claim's day-count is in the retrieved chunk):
```
grounded claim: "You have 45 days to file a dispute." | chunk: "customers have 45 days to file a dispute" | score: 0.93
detect on GROUNDED case   -> None      (expected None)
ungrounded claim: "Disputes must be raised within 60 days." | chunk: "the dispute window is 90 days"
detect on UNGROUNDED case -> FIRED ungrounded
```

**Full suite:** `python -m pytest -q` → **31 passed**.

## Follow-up: honest keyed ClaudeJudge regeneration (NOT run — needs API key, incurs cost)

```
"C:\Users\antho\AppData\Local\Programs\Python\Python312\python.exe" -m eval.published -n 1000 --seed 7 --label ClaudeJudge
```
Requires `ANTHROPIC_API_KEY` (loaded from `.env` via `load_local_env`; optional `JUDGE_MODEL`,
default `claude-opus-4-8`). Writes `reports/out/published.md` on the held-out slice
(`generate_dataset(..., held_out=True)`), including per-mode counts, transfer, ablation, and
reliability. This is where hybrid>heuristic on phantom should now become visible.
