"""Derive the compact input tables in data/inputs/ from three earlier public projects.

The committed CSVs are small extracts so the pipeline runs without the source repos.
To rebuild them, point the environment variables at local copies of the source repos:

  POS_REPO     -> ksa-pos-spending-dashboard   (SAMA weekly POS, via KAPSARC)
  COSTCO_REPO  -> costco-3-statement-dcf-sec   (SEC EDGAR XBRL companyfacts)
  LACITY_REPO  -> la-city-month-end-close-bva  (LA City Controller GL extracts)

`python -m vcomm.prepare` rewrites data/inputs/*.csv and data/inputs/manifest.json.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "inputs"
BASE = Path(os.environ.get("PORTFOLIO", "/workspace/portfolio"))
POS = Path(os.environ.get("POS_REPO", BASE / "ksa-pos-spending-dashboard"))
COSTCO = Path(os.environ.get("COSTCO_REPO", BASE / "_clones" / "costco-3-statement-dcf-sec"))
LACITY = Path(os.environ.get("LACITY_REPO", BASE / "_clones" / "la-city-month-end-close-bva"))

COSTCO_LINES = ["revenue", "sga", "ebit", "net_income", "cfo", "capex"]


def sama_sector_quarterly() -> pd.DataFrame:
    """Weekly SAMA POS value by sector -> calendar quarter (by week start date).

    Quarters hold 13 or 14 week starts, so the pipeline compares the *average weekly*
    value, not the quarter sum. Only dataset A (17 sectors, to 2025-07-06) has sectors.
    """
    p = POS / "data" / "processed"
    f = pd.read_csv(p / "fact_sector_weekly.csv", parse_dates=["week_start"])
    s = pd.read_csv(p / "dim_sector.csv")
    f = f.merge(s, on="sector_key")
    f["quarter"] = f["week_start"].dt.to_period("Q").astype(str)
    g = (f.groupby(["quarter", "sector_name"])
           .agg(weeks=("week_start", "nunique"), value_k_sar=("txn_value_k_sar", "sum"),
                txn_k=("txn_count_k", "sum"))
           .reset_index())
    return g


def costco_fy() -> pd.DataFrame:
    f = pd.read_csv(COSTCO / "data" / "facts_fy.csv")
    f = f[f["line"].isin(COSTCO_LINES)].copy()
    f["fiscal_year"] = pd.to_datetime(f["fy_end"]).dt.year
    return f[["fiscal_year", "fy_end", "line", "value", "tag"]].sort_values(["fiscal_year", "line"])


def lacity_gf() -> tuple[pd.DataFrame, pd.DataFrame]:
    """General Fund (fund 100) monthly postings and annual budget, by department."""
    pb = LACITY / "powerbi"
    dt = {"dept_code": str, "fund_code": str, "account_code": str}
    dept = pd.read_csv(pb / "dim_department.csv", dtype=dt)
    per = pd.read_csv(pb / "dim_period.csv")
    a = pd.read_csv(pb / "fct_actual_monthly.csv", dtype=dt)
    a = a[a["fund_code"] == "100"].merge(dept, on="dept_code").merge(per[["period_key", "month_start"]], on="period_key")
    m = (a.groupby(["fiscal_year", "fiscal_month", "month_start", "department_name"])["amount"].sum()
           .round(2).reset_index())
    b = pd.read_csv(pb / "fct_budget.csv", dtype=dt)
    b = b[b["fund_code"] == "100"].merge(dept, on="dept_code")
    cols = ["adopted_budget", "revised_budget", "actual_expense", "encumbrance", "total_expenditures"]
    bb = b.groupby(["fiscal_year", "department_name"])[cols].sum().round(2).reset_index()
    return m, bb


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tables = {
        "sama_pos_sector_quarterly.csv": sama_sector_quarterly(),
        "costco_fy.csv": costco_fy(),
    }
    m, bb = lacity_gf()
    tables["lacity_gf_monthly_by_department.csv"] = m
    tables["lacity_gf_budget_by_department.csv"] = bb
    manifest = {}
    for name, df in tables.items():
        path = OUT / name
        df.to_csv(path, index=False)
        manifest[name] = {"rows": int(len(df)), "sha256": _sha(path)}
        print(f"wrote {path} ({len(df)} rows)")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
