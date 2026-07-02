# FIX #3 — Making misrouting detection HONEST (removing the circular leak)

## 1. The circular leak (confirmed)

The misrouting detector graded itself against the answer key. It read the
ground-truth annotation `trace.intent_true` — a field a real production trace
would NEVER carry — directly inside the decision that fires the detector:

- `routing/routing.py:9` (old) — `if trace.intent_routed != trace.intent_true: return True`
- `routing/routing.py:12` (old) — `any(c.name != correct_tool(trace.intent_true) ...)`
- `features/heuristics.py:17` (old) — `intent_tool_mismatch = any(c.name != correct_tool(trace.intent_true) ...)`

Because `intent_true` is exactly the label the eval scores against, a detector
that reads it can never be wrong: precision/recall are structurally 1.0 by
construction, not because the detector works. That is circular and meaningless.

Note: two OTHER leaks were fixed separately and are preserved untouched here —
(1) the label-in-prompt leak (`parser/schema.py:to_judge_dict` + `detector/judge.py:86`),
and (2) the phantom/ungrounded tautology (`generator/generate.py` + `generator/phrasings.py`).

## 2. Intent-inference approach (the honest replacement)

New module `routing/intent.py` exposes `infer_intent(user_text) -> str | None`: a
deterministic, keyword/rule-based classifier over the USER's utterance (an
observable field a real trace carries). It maps phrasings to `INTENTS` keys:

- `policy_question` — "how long", "dispute window", "policy", "how many days" (checked FIRST so a policy question that mentions "dispute" is not misread as `dispute_charge`)
- `cancel_subscription` — "cancel", "unsubscribe", "end my plan/subscription"
- `request_refund` — "refund", "money back", "reimburse"
- `dispute_charge` — "dispute", "didn't make/authorize", "unauthorized", "fraud"
- `check_balance` — "balance", "how much do I have"

Rules are ordered; the first intent with a matching pattern wins. **No confident
match returns `None`** — the detector then does NOT fire (we never guess on an
underspecified utterance, to avoid manufacturing false positives).

`routing_mismatch(trace)` was rewritten to:
1. short-circuit to `False` on `behavioral_signals["user_correction"]` (a legit
   mid-conversation intent change is not a misroute — preserved behavior);
2. infer intent from the FIRST user turn's text;
3. return `False` if inference is `None` or no tool was called;
4. fire (`True`) when any invoked tool `!= correct_tool(inferred_intent)`.

## 3. `intent_true` reads: removed from detection vs. kept for eval

REMOVED from the detection path (what decides whether to fire):
- `routing/routing.py` `routing_mismatch` — both reads replaced by inferred intent.
- `features/heuristics.py` `intent_tool_mismatch` — now uses `infer_intent(first_user_text)`;
  the `RoutingDetector` `hits`/feature signal is therefore no longer leaky either.

KEPT (allowed — eval artifact, not detection path):
- `routing/routing.py` `intent_action_confusion` — the confusion-matrix helper still
  uses `t.intent_true` as its ground-truth axis. A confusion matrix is an eval/reporting
  artifact and is *expected* to reference ground truth. It never gates any detection.

Verification: `grep intent_true routing/routing.py features/heuristics.py routing/intent.py`
shows the only functional read is inside `intent_action_confusion`; every other hit is a
comment/docstring.

## 4. Honesty caveat — the detection ceiling (same spirit as spec §5)

Inferring intent from the current `USER_PHRASINGS` is trivially perfect: each intent
has disjoint, distinctive keywords, so `infer_intent` classifies every generated trace
correctly and misrouting precision/recall stay at 1.0.

This is strictly MORE honest than reading the label — the detector now infers from
observable text and *could* be wrong on a genuinely ambiguous utterance — but it is
still an EASY benchmark. Perfect numbers here mean "the keyword rules cover the
generator's phrasing vocabulary", NOT "misrouting detection is solved". Named openly,
in the spirit of spec §5's detection ceiling ("what this cannot catch yet").

**Follow-up (deferred):** adding ambiguous/underspecified user phrasings (e.g. "there's
a problem with my account", "help me with this charge") would let `infer_intent` make
real mistakes and produce honest FP/FN in misrouting. This was deliberately NOT done in
this fix because it risks perturbing the generator's clean-fraction distribution and the
`test_generate` invariants (clean_fraction ∈ [0.75, 0.85], both phantom intents present,
misrouting positives present, hard-negs clean). The core deliverable — removing the
circular `intent_true` read from the detection path — is complete and independent of it.

## 5. Proof (see report-back / Step 4)

- `routing_mismatch` returns `True` on the test misroute case (user "dispute this charge",
  tool `issue_refund`) and `False` on a clean case (user "dispute...", tool `file_dispute`)
  and `False` on a `user_correction` case — all via inference, no `intent_true`.
- `eval_mode("misrouting", generate_dataset(n=1000))` → tp=50, fp=0, fn=0, tn=950,
  precision=recall=f1=1.0, hard_negative_fp=0 (perfect-but-non-circular).
- Full suite: `31 passed`.
