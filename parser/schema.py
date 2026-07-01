from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

VALID_LABELS = {"phantom_action", "error_masking", "ungrounded", "misrouting", "clarification_loop"}

@dataclass
class ToolCall:
    name: str
    args: dict
    result: dict
    status: str
    latency_ms: int
    retrieved: Optional[list[dict]] = None

    @staticmethod
    def from_dict(d: dict) -> "ToolCall":
        return ToolCall(d["name"], d["args"], d["result"], d["status"], d["latency_ms"], d.get("retrieved"))

    def to_dict(self) -> dict:
        return {"name": self.name, "args": self.args, "result": self.result,
                "status": self.status, "latency_ms": self.latency_ms, "retrieved": self.retrieved}

@dataclass
class Turn:
    role: str
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "Turn":
        return Turn(d["role"], d["text"], [ToolCall.from_dict(c) for c in d.get("tool_calls", [])])

    def to_dict(self) -> dict:
        return {"role": self.role, "text": self.text, "tool_calls": [c.to_dict() for c in self.tool_calls]}

@dataclass
class Trace:
    conversation_id: str
    intent_true: str
    intent_routed: str
    injected_labels: list[str]
    turns: list[Turn]
    behavioral_signals: dict
    resolved: bool
    csat: Optional[float]
    timestamp: Optional[str] = None
    deploy_id: Optional[str] = None
    is_hard_negative: bool = False

    @staticmethod
    def from_dict(d: dict) -> "Trace":
        return Trace(d["conversation_id"], d["intent_true"], d["intent_routed"], list(d["injected_labels"]),
                     [Turn.from_dict(t) for t in d["turns"]], d["behavioral_signals"], d["resolved"],
                     d.get("csat"), d.get("timestamp"), d.get("deploy_id"), d.get("is_hard_negative", False))

    def to_dict(self) -> dict:
        return {"conversation_id": self.conversation_id, "intent_true": self.intent_true,
                "intent_routed": self.intent_routed, "injected_labels": self.injected_labels,
                "turns": [t.to_dict() for t in self.turns], "behavioral_signals": self.behavioral_signals,
                "resolved": self.resolved, "csat": self.csat, "timestamp": self.timestamp,
                "deploy_id": self.deploy_id, "is_hard_negative": self.is_hard_negative}

def validate(trace: Trace) -> list[str]:
    errors: list[str] = []
    if not trace.conversation_id:
        errors.append("missing conversation_id")
    for lbl in trace.injected_labels:
        if lbl not in VALID_LABELS:
            errors.append(f"unknown label: {lbl}")
    if trace.turns and trace.turns[0].role != "user":
        errors.append("first turn must be user")
    return errors
