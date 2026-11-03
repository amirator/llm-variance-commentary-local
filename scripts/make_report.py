#!/usr/bin/env python3
"""Builds reports/eval_table.md and reports/eval_chart.png from the committed eval outputs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"
def by_source(stem):
    """Split per-sheet outputs by source; LA City monthly and budget-vs-actual sheets are reported separately."""
    import glob
    out = {}
    for f in sorted(glob.glob(str(ROOT / "outputs" / stem / "*.json"))):
        r = json.load(open(f))
        d = "lacity_bva" if r["sheet_id"].startswith("lacity_bva") else (
            "lacity_monthly" if r["sheet_id"].startswith("lacity") else r["domain"])
        b = out.setdefault(d, {"sheets": 0, "first_pass": 0, "llm_final": 0})
        b["sheets"] += 1
        b["first_pass"] += int(r["passed_first"])
        b["llm_final"] += int(r["source"] == "llm")
    return out


MODELS = [("qwen2.5-1.5b-instruct-q4_k_m", "Qwen2.5-1.5B-Instruct Q4_K_M"),
          ("qwen2.5-0.5b-instruct-q4_k_m", "Qwen2.5-0.5B-Instruct Q4_K_M")]
DOM = {"sama_pos": "SAMA POS (quarterly YoY)", "costco_sec": "Costco SEC (fiscal-year YoY)",
       "lacity_monthly": "LA City GF (monthly YoY)", "lacity_bva": "LA City GF (budget vs actual)"}
ISSUES = ["unsupported_number", "missing_driver", "wrong_direction", "unsupported_claim", "unit_mismatch",
          "unsupported_entity", "missing_headline", "unsupported_period", "wrong_currency", "format"]


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "-"


def main():
    S = {m: json.loads((REP / f"summary_{m}.json").read_text()) for m, _ in MODELS}
    st = json.loads((REP / "validator_stress_test.json").read_text())
    L = ["# Evaluation results", "",
         "35 fact sheets (16 SAMA quarters, 5 Costco fiscal years, 12 LA City months, 2 LA City budget years).",
         "Each sheet gets up to 3 model attempts; if none passes the validator, the deterministic template is used.",
         "Temperature 0.3, top-p 0.9, seed 7 + attempt number, CPU only (8 threads).", "",
         "## Headline", "",
         "| Model | First-attempt pass | Passed within 3 attempts | Template fallback | Attempt pass rate | Mean s / attempt |",
         "|---|---|---|---|---|---|"]
    for m, name in MODELS:
        s = S[m]
        L.append(f"| {name} | {pct(s['first_attempt_pass'], s['sheets'])} | {pct(s['llm_final'], s['sheets'])} | "
                 f"{pct(s['template_fallback'], s['sheets'])} | {100 * s['attempt_pass_rate']:.0f}% of {s['attempts']} | "
                 f"{s['mean_seconds_per_attempt']} |")
    L += ["", "## By source", "", "| Source | " + " | ".join(f"{n}: first / within 3" for _, n in MODELS) + " |",
          "|---|" + "---|" * len(MODELS)]
    for d, dn in DOM.items():
        cells = []
        for m, _ in MODELS:
            b = by_source(m).get(d)
            cells.append(f"{b['first_pass']}/{b['sheets']} / {b['llm_final']}/{b['sheets']}" if b else "-")
        L.append(f"| {dn} | " + " | ".join(cells) + " |")
    L += ["", "## Why drafts were rejected", "",
          "Share of all model attempts that had at least one issue of each type (an attempt can have several).", "",
          "| Issue type | " + " | ".join(n for _, n in MODELS) + " |", "|---|" + "---|" * len(MODELS)]
    for t in ISSUES:
        L.append(f"| {t} | " + " | ".join(
            f"{S[m]['attempts_with_issue_type'].get(t, 0)} of {S[m]['attempts']}" for m, _ in MODELS) + " |")
    L += ["", "## Validator stress test", "",
          "Synthetic corruptions applied to every model draft that passed (see `src/vcomm/mutate.py`).", "",
          "| Corruption | Cases | Caught | Rate |", "|---|---|---|---|"]
    for k, v in st.items():
        L.append(f"| {k} | {v['cases']} | {v['caught']} | {100 * v['rate']:.0f}% |" if v["rate"] is not None
                 else f"| {k} | 0 | - | - |")
    (REP / "eval_table.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=150)
    labels = ["First attempt", "Within 3 attempts", "Template fallback"]
    w = 0.38
    for i, (m, name) in enumerate(MODELS):
        s = S[m]
        vals = [s["first_attempt_pass"], s["llm_final"], s["template_fallback"]]
        xs = [j + (i - 0.5) * w for j in range(3)]
        bars = ax.bar(xs, vals, w, label=name, color=["#2563eb", "#93c5fd"][i])
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.5, str(v), ha="center", fontsize=8)
    ax.set_xticks(range(3), labels)
    ax.set_ylabel("fact sheets (of 35)")
    ax.set_ylim(0, 38)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("Fact sheets by validator outcome (35 sheets, up to 3 attempts each)", fontsize=10)
    fig.tight_layout()
    fig.savefig(REP / "eval_chart.png")


if __name__ == "__main__":
    main()
