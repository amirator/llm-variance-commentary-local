"""Deterministic fallback: a plain commentary assembled from the fact sheet's display strings.

Used when the model fails validation on every attempt. It is validated like any draft.
"""
from __future__ import annotations

from .facts import FactSheet


def _dir(v: float) -> str:
    return "up" if v > 0 else "down" if v < 0 else "unchanged"


def _abs(display: str) -> str:
    return display.lstrip("+-")


def template_commentary(s: FactSheet) -> str:
    f = {x.key: x for x in s.facts}
    if s.domain == "sama_pos":
        t = (f"Average weekly point-of-sale spending in Saudi Arabia was {f['total_value_cur'].display} in {s.period}, "
             f"{_dir(f['total_value_yoy'].value)} {_abs(f['total_value_yoy'].display)} from {f['total_value_prev'].display} in {s.comparison_period}. "
             f"Average weekly transactions were {f['txn_cur'].display} ({_dir(f['txn_yoy'].value)} {_abs(f['txn_yoy'].display)}), "
             f"and the average ticket was {f['ticket_cur'].display} ({_dir(f['ticket_yoy'].value)} {_abs(f['ticket_yoy'].display)}). ")
    elif s.domain == "costco_sec":
        t = (f"Costco revenue was {f['revenue_cur'].display} in {s.period}, {_dir(f['revenue_yoy'].value)} "
             f"{_abs(f['revenue_yoy'].display)} from {f['revenue_prev'].display} in {s.comparison_period}. "
             f"Operating margin was {f['op_margin_cur'].display} ({_dir(f['op_margin_chg'].value)} {_abs(f['op_margin_chg'].display)}), "
             f"with SG&A at {f['sga_pct_cur'].display} of revenue. ")
    elif s.id.startswith("lacity_bva"):
        t = (f"The General Fund revised budget for {s.period} was {f['revised'].display}, against an adopted budget of "
             f"{f['adopted'].display}. Committed spend was {f['committed'].display}, a utilisation of {f['utilisation'].display}, "
             f"leaving {f['unspent'].display} unspent. ")
        parts = []
        for i, d in enumerate(s.drivers, 1):
            parts.append(f"{d.name} used {f[f'low{i}_util'].display} of a {f[f'low{i}_revised'].display} budget")
        return t + "Departments with the lowest utilisation: " + "; ".join(parts) + "."
    else:
        t = (f"General Fund postings were {f['total_cur'].display} in {s.period}, {_dir(f['total_yoy'].value)} "
             f"{_abs(f['total_yoy'].display)} from {f['total_prev'].display} in {s.comparison_period}. "
             f"Year-to-date postings were {f['ytd_cur'].display}, {_dir(f['ytd_yoy'].value)} {_abs(f['ytd_yoy'].display)}. ")
    parts = []
    for d in s.drivers[:3]:
        chg = next(x for x in s.facts if x.entity == d.name and x.kind == "change" and x.unit == "money")
        word = "increased" if d.change > 0 else "decreased"
        parts.append(f"{d.name} {word} by {_abs(chg.display)}")
    return t + "The largest movements were: " + "; ".join(parts) + "."
