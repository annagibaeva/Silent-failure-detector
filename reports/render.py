from __future__ import annotations
from guardrails.specs import guardrail_for

def render_markdown(ranked, groups) -> str:
    lines = ["# Silent-Failure Report", ""]
    for i, row in enumerate(ranked, 1):
        sig = row["signature"]
        lines += [f"## #{i} — {sig[0]} ({sig[1]} → {sig[2]})",
                  f"- **Frequency:** {row['freq']}  **Severity:** {row['severity']}  **Score:** {row['score']}",
                  f"- **Root-cause hypothesis:** tool `{sig[2]}` returned `{sig[3]}` while the agent claimed success.",
                  f"- **Guardrail to ship:** {guardrail_for(sig[0], sig[2])}",
                  "- **Examples:**"]
        for det, tr in groups[row["signature_id"]]["members"][:3]:
            lines.append(f"  - `{tr.conversation_id}`: “…{det.evidence_span}…”")
        lines.append("")
    return "\n".join(lines)
