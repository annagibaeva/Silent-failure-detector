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
    """Real judge. Lazy anthropic import keeps the core spine key-free."""
    def __init__(self, model: str = "claude-opus-4-8", api_key: Optional[str] = None, prompt_version: str = "v1"):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._pv = prompt_version

    @staticmethod
    def _parse_verdict_json(raw: str) -> dict:
        import json
        import re
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        for candidate in (text,):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                start = candidate.find("{")
                if start >= 0:
                    depth = 0
                    for i, ch in enumerate(candidate[start:], start):
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                            if depth == 0:
                                try:
                                    return json.loads(candidate[start : i + 1])
                                except json.JSONDecodeError:
                                    break
        mode_m = re.search(r'"failure_mode"\s*:\s*(?:"([^"]*)"|null)', text, re.I)
        conf_m = re.search(r'"confidence"\s*:\s*([0-9.]+)', text, re.I)
        span_m = re.search(r'"evidence_span"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.I | re.S)
        if mode_m or conf_m or span_m:
            fm = mode_m.group(1) if mode_m and mode_m.group(1) is not None else None
            if mode_m and "null" in mode_m.group(0).lower() and fm is None:
                fm = None
            return {
                "failure_mode": fm,
                "confidence": float(conf_m.group(1)) if conf_m else 0.0,
                "evidence_span": span_m.group(1) if span_m else "",
            }
        raise ValueError(f"could not parse judge JSON: {raw[:200]!r}")

    def assess(self, question: str, trace: Trace) -> Verdict:
        import json
        prompt = (f"{question}\n"
                  f"Reply with a single JSON object only (double-quoted keys/strings, no markdown): "
                  f'{{"failure_mode": string|null, "confidence": number, "evidence_span": string}}\n'
                  f"evidence_span MUST be a verbatim substring of the conversation.\n"
                  f"CONVERSATION:\n{json.dumps(trace.to_dict())}")
        msg = self._client.messages.create(model=self._model, max_tokens=300,
                                           messages=[{"role": "user", "content": prompt}])
        data = self._parse_verdict_json(msg.content[0].text)
        usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
        return Verdict(data.get("failure_mode"), float(data.get("confidence", 0.0)),
                       data.get("evidence_span", ""), self._model, self._pv, usage)


class CachingJudge:
    """Reuse verdicts when the same trace is judged again with the same question."""

    def __init__(self, inner: Judge):
        self._inner = inner
        self._cache: dict[tuple[str, str], Verdict] = {}
        self.api_calls = 0
        self.cache_hits = 0

    def assess(self, question: str, trace: Trace) -> Verdict:
        key = (trace.conversation_id, question)
        if key in self._cache:
            self.cache_hits += 1
            return self._cache[key]
        self.api_calls += 1
        if self.api_calls % 50 == 0:
            print(f"judge: {self.api_calls} API calls, {self.cache_hits} cache hits", flush=True)
        verdict = self._inner.assess(question, trace)
        self._cache[key] = verdict
        return verdict


def make_claude_judge(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    cache: bool = True,
) -> Judge:
    import os
    model = model or os.environ.get("JUDGE_MODEL", "claude-opus-4-8")
    inner = ClaudeJudge(model=model, api_key=api_key)
    return CachingJudge(inner) if cache else inner
