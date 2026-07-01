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
    def detect(self, trace: Trace, judge: Judge, threshold: Optional[float] = None) -> Optional[Detection]:
        thr = threshold if threshold is not None else threshold_for(self.mode)
        hits = [k for k, v in extract(trace).items() if v is True]
        v = judge.assess(self.question, trace)          # trace is already redacted by the caller
        if v.failure_mode != self.mode or v.confidence < thr:
            return None
        if not grounds(v.evidence_span, trace):          # impr 2: reject verdicts the judge can't point at
            return None
        return Detection(trace.conversation_id, self.mode, SEVERITY[self.mode],
                         v.confidence, v.evidence_span, hits)

class PhantomDetector(_JudgeDetector):
    mode = "phantom_action"
    question = "Does the response claim an outcome the tool results don't support?"

DETECTORS: dict[str, Detector] = {"phantom_action": PhantomDetector()}
