# detector/judge.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol
from parser.schema import Trace
from generator.tools import CONFIRM_WORDS

@dataclass
class Verdict:
    failure_mode: Optional[str]
    confidence: float
    evidence_span: str
    model_version: str = "stub"
    prompt_version: str = "v1"
    usage: Optional[dict] = None

class Judge(Protocol):
    def assess(self, question: str, trace: Trace) -> Verdict: ...

class StubJudge:
    """Deterministic, key-free naive baseline for CI. Phantom-only by design."""
    def assess(self, question: str, trace: Trace) -> Verdict:
        agents = [t for t in trace.turns if t.role == "agent"]
        if not agents:
            return Verdict(None, 0.0, "")
        last = agents[-1]
        failed = any(c.result.get("success") is False for c in last.tool_calls)
        hit = next((w for w in CONFIRM_WORDS if w in last.text.lower()), None)
        if failed and hit:
            idx = last.text.lower().index(hit)
            return Verdict("phantom_action", 0.9, last.text[idx:idx + len(hit)])
        return Verdict(None, 0.1, "")

class ClaudeJudge:
    """Real judge (temp 0). Lazy anthropic import keeps the core spine key-free."""
    def __init__(self, model: str = "claude-opus-4-8", api_key: Optional[str] = None, prompt_version: str = "v1"):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._pv = prompt_version

    def assess(self, question: str, trace: Trace) -> Verdict:
        import json
        prompt = (f"{question}\nReturn JSON {{failure_mode, confidence, evidence_span}}. "
                  f"evidence_span MUST be a verbatim substring of the conversation.\n"
                  f"CONVERSATION:\n{json.dumps(trace.to_dict())}")
        msg = self._client.messages.create(model=self._model, max_tokens=300, temperature=0,
                                           messages=[{"role": "user", "content": prompt}])
        data = json.loads(msg.content[0].text)
        usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
        return Verdict(data.get("failure_mode"), float(data.get("confidence", 0.0)),
                       data.get("evidence_span", ""), self._model, self._pv, usage)
