"""Prompt construction. The model sees only the fact sheet, rendered as plain lines."""
from __future__ import annotations

from .facts import FactSheet

SYSTEM = (
    "You are a finance analyst writing a short management commentary on a variance report. "
    "Use ONLY the facts you are given. Copy every number exactly as it is written in the facts, "
    "including its unit (%, pp, $, SAR, bn, mn, m). Do not calculate new numbers. Do not mention "
    "any company, sector, department, event, cause or outlook that is not in the facts, and do not "
    "interpret what the numbers say about efficiency, demand or financial health. Every comparison is with "
    "the comparison period stated in the facts, never with the previous quarter or month. "
    "Write one plain-text paragraph of 3 to 5 sentences, with no headings, bullets or markdown."
)


def render_facts(sheet: FactSheet) -> str:
    lines = [f"Subject: {sheet.subject}", f"Period: {sheet.period} compared with {sheet.comparison_period} ({sheet.comparison})", "Facts:"]
    for f in sheet.facts:
        lines.append(f"- {f.label}: {f.display}")
    if sheet.drivers and sheet.comparison != "budget vs actual":
        basis = "% change" if sheet.domain == "costco_sec" else "size of change"
        lines.append(f"Largest movers (by {basis}): " + "; ".join(
            f"{d.name} ({'up' if d.change > 0 else 'down'})" for d in sheet.drivers))
    elif sheet.drivers:
        lines.append("Lowest budget utilisation: " + "; ".join(d.name for d in sheet.drivers))
    for n in sheet.notes:
        lines.append(f"Note: {n}")
    return "\n".join(lines)


def build_messages(sheet: FactSheet, feedback: list[str] | None = None, previous: str | None = None) -> list[dict]:
    """First attempt: facts + task. Retries: a fresh prompt that lists what the checker rejected
    (replaying the rejected draft made small models copy it verbatim)."""
    h = sheet.fact(sheet.headline_key)
    task = (
        f"{render_facts(sheet)}\n\n"
        f"Write the commentary for {sheet.period}. The first sentence must state {h.label.lower()} ({h.display}). "
        f"You must name {' and '.join(sheet.required)} and give their figures. "
        "Use 'up'/'increased' for positive changes and 'down'/'decreased' for negative changes. "
        "Do not start with a title."
    )
    if feedback:
        task += ("\n\nAn earlier draft was rejected by a fact checker for these reasons:\n- " + "\n- ".join(feedback)
                 + "\nAvoid all of these mistakes. Every number must appear in the facts list above.")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
