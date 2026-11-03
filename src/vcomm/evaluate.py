"""Run a generator over every fact sheet, save drafts + validation reports, summarise."""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from statistics import mean

from .facts import FactSheet
from .mutate import MUTATIONS
from .pipeline import draft
from .validate import validate


def run_model(sheets: list[FactSheet], gen, out_dir: Path, max_attempts: int = 3) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, t0 = [], time.time()
    for s in sheets:
        o = draft(s, gen, max_attempts=max_attempts)
        rec = {"sheet_id": s.id, "domain": s.domain, "title": s.title, "source": o.source,
               "passed_first": o.passed_first, "attempts": o.attempts, "final_text": o.final_text,
               "final_report": o.final_report}
        (out_dir / f"{s.id}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
        (out_dir / f"{s.id}.md").write_text(
            f"# {s.title}\n\nSource: **{o.source}** ({len(o.attempts)} model attempt(s), "
            f"first attempt {'passed' if o.passed_first else 'failed'})\n\n{o.final_text}\n")
        rows.append(rec)
        print(f"{s.id:24s} {o.source:8s} attempts={len(o.attempts)}", flush=True)
    return summarise(rows, getattr(gen, "name", "?"), time.time() - t0)


def summarise(rows: list[dict], model: str, seconds: float) -> dict:
    n = len(rows)
    att = [a for r in rows for a in r["attempts"]]
    issue_attempts = Counter(t for a in att for t in {i["type"] for i in a["issues"]})
    issue_total = Counter(i["type"] for a in att for i in a["issues"])
    by_domain = {}
    for d in sorted({r["domain"] for r in rows}):
        rr = [r for r in rows if r["domain"] == d]
        by_domain[d] = {"sheets": len(rr), "first_pass": sum(r["passed_first"] for r in rr),
                        "llm_final": sum(r["source"] == "llm" for r in rr)}
    secs = [a["usage"].get("seconds") for a in att if a.get("usage", {}).get("seconds")]
    toks = [a["usage"].get("completion_tokens") for a in att if a.get("usage", {}).get("completion_tokens")]
    return {
        "model": model, "sheets": n, "attempts": len(att),
        "first_attempt_pass": sum(r["passed_first"] for r in rows),
        "llm_final": sum(r["source"] == "llm" for r in rows),
        "template_fallback": sum(r["source"] == "template" for r in rows),
        "attempt_pass_rate": round(sum(a["passed"] for a in att) / len(att), 4) if att else None,
        "attempts_with_issue_type": dict(issue_attempts.most_common()),
        "issues_total_by_type": dict(issue_total.most_common()),
        "by_domain": by_domain,
        "mean_seconds_per_attempt": round(mean(secs), 1) if secs else None,
        "mean_completion_tokens": round(mean(toks), 1) if toks else None,
        "wall_seconds": round(seconds, 1),
    }


def stress_test(sheets: dict[str, FactSheet], texts: list[tuple[str, str]]) -> dict:
    """Apply each synthetic corruption to clean, validated texts; count how many are caught."""
    res = {}
    for name, fn in MUTATIONS.items():
        n = caught = 0
        missed = []
        for sid, text in texts:
            assert validate(text, sheets[sid]).passed
            bad = fn(text, sheets[sid])
            if bad is None or bad == text:
                continue
            n += 1
            if not validate(bad, sheets[sid]).passed:
                caught += 1
            elif len(missed) < 3:
                missed.append({"sheet": sid, "text": bad})
        res[name] = {"cases": n, "caught": caught, "rate": round(caught / n, 4) if n else None, "missed_examples": missed}
    return res
