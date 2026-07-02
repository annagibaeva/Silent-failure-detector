# detector/detect.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol
from parser.schema import Trace
from features.heuristics import extract
from detector.judge import Judge
from detector.calibrate import threshold_for
from generator.tools import SEVERITY

@dataclass
class Detection:
    conversation_id: str
    failure_mode: str
    severity: int
    confidence: float
    evidence_span: str
    heuristics_hit: list[str]

def grounds(span: str, trace: Trace) -> bool:
    if not span:
        return False
    hay = " ".join(t.text for t in trace.turns)
    hay += " " + " ".join(str(c.result) for turn in trace.turns for c in turn.tool_calls)
    return span in hay

class Detector(Protocol):
    mode: str
    def detect(self, trace: Trace, judge: Judge, threshold: Optional[float] = None) -> Optional[Detection]: ...

class _JudgeDetector:
    mode = ""
    question = ""

    def _mode_directive(self) -> str:
        """Instruct the judge to answer in the project's canonical taxonomy so a correct
        detection uses the EXACT mode string the detector compares against below."""
        return (f'If the failure described is present, set "failure_mode" to the EXACT '
                f'string "{self.mode}"; otherwise set "failure_mode" to null.')

    def detect(self, trace: Trace, judge: Judge, threshold: Optional[float] = None) -> Optional[Detection]:
        thr = threshold if threshold is not None else threshold_for(self.mode)
        hits = [k for k, v in extract(trace).items() if v is True]
        # Tell the judge which canonical taxonomy string to answer with when the failure
        # is present. This is NOT a ground-truth leak: it only names the mode the question
        # is *about* (a yes/no framing); the trace's real label is never disclosed. Without
        # this the judge invents synonyms (e.g. "unsupported_outcome_claim") that never
        # match self.mode below, silently discarding every true detection.
        question = f"{self.question}\n{self._mode_directive()}"
        v = judge.assess(question, trace)               # trace is already redacted by the caller
        if v.failure_mode != self.mode or v.confidence < thr:
            return None
        if not grounds(v.evidence_span, trace):          # impr 2: reject verdicts the judge can't point at
            return None
        return Detection(trace.conversation_id, self.mode, SEVERITY[self.mode],
                         v.confidence, v.evidence_span, hits)

class PhantomDetector(_JudgeDetector):
    mode = "phantom_action"
    question = "Does the response claim an outcome the tool results don't support?"

class UngroundedDetector(_JudgeDetector):
    mode = "ungrounded"
    question = "Is every factual claim grounded in a retrieved chunk above threshold?"

from routing.routing import routing_mismatch

class RoutingDetector:
    mode = "misrouting"
    def detect(self, trace, judge=None, threshold=None):
        if not routing_mismatch(trace):
            return None
        agents = [t for t in trace.turns if t.role == "agent"]
        span = agents[-1].text if agents else ""
        return Detection(trace.conversation_id, self.mode, SEVERITY[self.mode], 1.0, span,
                         ["intent_tool_mismatch"])

DETECTORS: dict[str, Detector] = {"phantom_action": PhantomDetector(), "ungrounded": UngroundedDetector()}
DETECTORS["misrouting"] = RoutingDetector()
