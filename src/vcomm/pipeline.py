"""Draft -> validate -> retry with feedback -> deterministic fallback."""
from __future__ import annotations

from dataclasses import dataclass, field

from .facts import FactSheet
from .prompt import build_messages
from .template import template_commentary
from .validate import validate


@dataclass
class Outcome:
    sheet_id: str
    final_text: str
    source: str                   # "llm" | "template"
    attempts: list[dict] = field(default_factory=list)
    final_report: dict = field(default_factory=dict)

    @property
    def passed_first(self) -> bool:
        return bool(self.attempts) and self.attempts[0]["passed"]


def draft(sheet: FactSheet, gen, max_attempts: int = 3, seed: int = 7) -> Outcome:
    out = Outcome(sheet.id, "", "template")
    prev, feedback = None, None
    for a in range(max_attempts):
        msgs = build_messages(sheet, feedback, prev)
        text = gen(msgs, seed + a)
        rep = validate(text, sheet)
        out.attempts.append({"attempt": a + 1, "text": text, "passed": rep.passed,
                             "issues": [i.__dict__ for i in rep.issues], "usage": getattr(gen, "last_usage", {})})
        if rep.passed:
            out.final_text, out.source, out.final_report = text, "llm", rep.to_dict()
            return out
        prev, feedback = text, [i.detail for i in rep.issues][:8]  # prev kept for the record only
    text = template_commentary(sheet)
    rep = validate(text, sheet)
    if not rep.passed:  # the fallback itself must be clean; fail loudly if not
        raise AssertionError(f"template failed validation for {sheet.id}: {[i.detail for i in rep.issues]}")
    out.final_text, out.source, out.final_report = text, "template", rep.to_dict()
    return out
