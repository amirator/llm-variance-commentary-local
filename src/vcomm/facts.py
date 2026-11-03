"""Deterministic variance engine: input tables -> structured JSON fact sheets.

Every number the LLM is allowed to say lives in a fact sheet. Each fact carries its
raw value, a unit class used by the validator, and a display string with the exact
rounding the prompt shows to the model.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "data" / "inputs"

# unit classes understood by the validator
PCT, PP, MONEY, COUNT = "pct", "pp", "money", "count"
SCALE = {"bn": 1e9, "mn": 1e6, "k": 1e3, "": 1.0}


@dataclass
class Fact:
    key: str
    label: str
    value: float              # base units (e.g. SAR, USD, transactions) or percent / pp
    unit: str                 # pct | pp | money | count
    kind: str                 # level | change
    display: str              # how the prompt writes it
    decimals: int
    scale: str = ""           # bn | mn | k | "" (display scale for money/count)
    currency: str | None = None
    entity: str | None = None  # driver/metric this fact belongs to


@dataclass
class Driver:
    name: str
    aliases: list[str]
    change: float             # signed change in base units
    change_pct: float | None
    rank: int


@dataclass
class FactSheet:
    id: str
    domain: str
    title: str
    subject: str
    period: str
    comparison_period: str
    comparison: str
    currency: str
    facts: list[Fact]
    drivers: list[Driver]
    required: list[str]               # driver names that must be mentioned
    headline_key: str                 # fact key that must be cited
    period_tokens: list[str]          # years / labels that may appear in text
    other_entities: list[str] = field(default_factory=list)  # in-domain names NOT in this sheet
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "FactSheet":
        d = dict(d)
        d["facts"] = [Fact(**f) for f in d["facts"]]
        d["drivers"] = [Driver(**x) for x in d["drivers"]]
        return FactSheet(**d)

    def fact(self, key: str) -> Fact:
        return next(f for f in self.facts if f.key == key)


# ---- formatting helpers ----------------------------------------------------
def money(v: float, cur: str, scale: str, dp: int, signed: bool = False) -> str:
    sym = "$" if cur == "USD" else "SAR "
    x = v / SCALE[scale]
    sign = ("+" if x >= 0 else "-") if signed else ("-" if x < 0 else "")
    unit = {"bn": " bn", "mn": " mn", "k": "k", "": ""}[scale] if cur == "SAR" else {"bn": "bn", "mn": "m", "k": "k", "": ""}[scale]
    return f"{sign}{sym}{abs(x):,.{dp}f}{unit}"


def pct(v: float, dp: int = 1, signed: bool = True) -> str:
    return f"{v:+.{dp}f}%" if signed else f"{v:.{dp}f}%"


def updown(v: float) -> str:
    return "up" if v > 0 else "down" if v < 0 else "flat"


def mfact(key, label, v, cur, scale, dp, kind="level", entity=None) -> Fact:
    return Fact(key, label, float(v), MONEY, kind, money(v, cur, scale, dp, signed=(kind == "change")),
                dp, scale, cur, entity)


def pfact(key, label, v, dp=1, kind="change", unit=PCT, entity=None) -> Fact:
    disp = (f"{v:+.{dp}f} pp" if unit == PP else pct(v, dp)) if kind == "change" else f"{v:.{dp}f}%"
    return Fact(key, label, float(v), unit, kind, disp, dp, "", None, entity)


def cfact(key, label, v, scale, dp, kind="level", entity=None) -> Fact:
    x = v / SCALE[scale]
    word = {"bn": " billion", "mn": " million", "k": " thousand", "": ""}[scale]
    disp = (f"{x:+,.{dp}f}" if kind == "change" else f"{x:,.{dp}f}") + word
    return Fact(key, label, float(v), COUNT, kind, disp, dp, scale, None, entity)


# ---- SAMA point-of-sale: quarter vs same quarter last year -------------------
SAMA_ALIASES = {
    "Restaurants & Café": ["restaurants & café", "restaurants & cafe", "restaurants and cafés",
                           "restaurants and cafes", "restaurants", "café", "cafe"],
    "Beverage and Food": ["beverage and food", "food and beverage", "beverages and food", "food & beverage"],
    "Miscellaneous Goods and Services": ["miscellaneous goods and services", "miscellaneous goods", "miscellaneous"],
    "Construction & Building Materials": ["construction & building materials", "construction and building materials",
                                          "building materials", "construction"],
    "Electronic & Electric Devices": ["electronic & electric devices", "electronic and electric devices", "electronics"],
    "Recreation and Culture": ["recreation and culture", "recreation"],
    "Clothing and Footwear": ["clothing and footwear", "clothing", "footwear"],
    "Public Utilities": ["public utilities", "utilities"],
    "Gas Stations": ["gas stations", "fuel stations", "petrol stations"],
    "Telecommunication": ["telecommunication", "telecommunications", "telecom"],
    "Other": ["other sector", "\"other\"", "'other'", "other category", "other (unclassified)"],
}


def _aliases(name: str, table: dict) -> list[str]:
    return table.get(name, [name.lower()])


def sama_sheets() -> list[FactSheet]:
    df = pd.read_csv(INPUTS / "sama_pos_sector_quarterly.csv")
    q = df.groupby("quarter").agg(weeks=("weeks", "max"), value=("value_k_sar", "sum"), txn=("txn_k", "sum"))
    all_sectors = sorted(df["sector_name"].unique())
    quarters = list(q.index)
    sheets = []
    for cur in quarters:
        prev = str(pd.Period(cur, "Q") - 4)
        if prev not in q.index or q.loc[cur, "weeks"] < 12 or q.loc[prev, "weeks"] < 12:
            continue
        wc, wp = int(q.loc[cur, "weeks"]), int(q.loc[prev, "weeks"])
        vc, vp = q.loc[cur, "value"] * 1e3 / wc, q.loc[prev, "value"] * 1e3 / wp     # SAR per week
        tc, tp = q.loc[cur, "txn"] * 1e3 / wc, q.loc[prev, "txn"] * 1e3 / wp
        kc, kp = vc / tc, vp / tp
        pc, pp_ = pd.Period(cur, "Q"), pd.Period(prev, "Q")
        lab_c, lab_p = f"Q{pc.quarter} {pc.year}", f"Q{pp_.quarter} {pp_.year}"
        s = df[df["quarter"].isin([cur, prev])].pivot_table(index="sector_name", columns="quarter",
                                                            values="value_k_sar", aggfunc="sum")
        wk = df[df["quarter"].isin([cur, prev])].groupby("quarter")["weeks"].max()
        s = s.div(wk, axis=1) * 1e3
        s["chg"] = s[cur] - s[prev]
        s["chg_pct"] = (s[cur] / s[prev] - 1) * 100
        up = s[s.chg > 0].sort_values("chg", ascending=False).head(3)
        dn = s[s.chg < 0].sort_values("chg").head(2)
        drv = pd.concat([up, dn]).assign(a=lambda x: x.chg.abs()).sort_values("a", ascending=False)
        facts = [
            mfact("total_value_cur", f"Average weekly POS value, {lab_c}", vc, "SAR", "bn", 2),
            mfact("total_value_prev", f"Average weekly POS value, {lab_p}", vp, "SAR", "bn", 2),
            pfact("total_value_yoy", "Average weekly POS value, change vs same quarter last year", (vc / vp - 1) * 100),
            mfact("total_value_chg", "Average weekly POS value, change", vc - vp, "SAR", "bn", 2, "change"),
            cfact("txn_cur", f"Average weekly transactions, {lab_c}", tc, "mn", 1),
            cfact("txn_prev", f"Average weekly transactions, {lab_p}", tp, "mn", 1),
            pfact("txn_yoy", "Average weekly transactions, change vs same quarter last year", (tc / tp - 1) * 100),
            mfact("ticket_cur", f"Average ticket, {lab_c}", kc, "SAR", "", 1),
            mfact("ticket_prev", f"Average ticket, {lab_p}", kp, "SAR", "", 1),
            pfact("ticket_yoy", "Average ticket, change vs same quarter last year", (kc / kp - 1) * 100),
        ]
        drivers = []
        for i, (name, r) in enumerate(drv.iterrows(), 1):
            k = f"drv{i}"
            facts.append(mfact(f"{k}_chg", f"{name}: change in average weekly value", r.chg, "SAR", "mn", 0, "change", name))
            facts.append(pfact(f"{k}_yoy", f"{name}: change vs same quarter last year", r.chg_pct, entity=name))
            facts.append(mfact(f"{k}_cur", f"{name}: average weekly value, {lab_c}", r[cur], "SAR", "mn", 0, entity=name))
            facts.append(mfact(f"{k}_prev", f"{name}: average weekly value, {lab_p}", r[prev], "SAR", "mn", 0, entity=name))
            drivers.append(Driver(name, _aliases(name, SAMA_ALIASES), float(r.chg), float(r.chg_pct), i))
        named = {d.name for d in drivers}
        sheets.append(FactSheet(
            id=f"sama_pos_{cur}", domain="sama_pos",
            title=f"Saudi point-of-sale spending, {lab_c} vs {lab_p}",
            subject="Saudi Arabia point-of-sale card spending (SAMA weekly statistics)",
            period=lab_c, comparison_period=lab_p, comparison="year over year", currency="SAR",
            facts=facts, drivers=drivers, required=[d.name for d in drivers[:2]],
            headline_key="total_value_yoy",
            period_tokens=sorted({str(pc.year), str(pp_.year), f"Q{pc.quarter}", f"Q{pp_.quarter}"}),
            other_entities=[x for x in all_sectors if x not in named],
            notes=[f"Quarters are grouped by week start date ({wc} weeks vs {wp} weeks), so averages per week are compared."],
        ))
    return sheets


# ---- Costco: fiscal year vs prior fiscal year --------------------------------
COSTCO_METRICS = {
    "ebit": ("Operating income", ["operating income", "operating profit", "ebit"]),
    "net_income": ("Net income", ["net income", "net profit", "net earnings"]),
    "sga": ("SG&A", ["sg&a", "selling, general and administrative", "selling, general & administrative"]),
    "cfo": ("Operating cash flow", ["operating cash flow", "cash from operations", "cash flow from operations",
                                    "cash generated from operations", "operating cash"]),
    "capex": ("Capital expenditure", ["capital expenditure", "capital expenditures", "capex", "capital spending"]),
}
COSTCO_OTHERS = ["Walmart", "Amazon", "Target", "Sam's Club", "BJ's", "Kroger", "Kirkland"]


def costco_sheets() -> list[FactSheet]:
    df = pd.read_csv(INPUTS / "costco_fy.csv")
    p = df.pivot_table(index="fiscal_year", columns="line", values="value")
    sheets = []
    for fy in p.index[1:]:
        c, b = p.loc[fy], p.loc[fy - 1]
        rev_yoy = (c.revenue / b.revenue - 1) * 100
        om_c, om_p = c.ebit / c.revenue * 100, b.ebit / b.revenue * 100
        sg_c, sg_p = c.sga / c.revenue * 100, b.sga / b.revenue * 100
        facts = [
            mfact("revenue_cur", f"Revenue, FY{fy}", c.revenue, "USD", "bn", 1),
            mfact("revenue_prev", f"Revenue, FY{fy-1}", b.revenue, "USD", "bn", 1),
            pfact("revenue_yoy", "Revenue, change vs prior year", rev_yoy),
            mfact("revenue_chg", "Revenue, change", c.revenue - b.revenue, "USD", "bn", 1, "change"),
            pfact("op_margin_cur", f"Operating margin, FY{fy}", om_c, 2, "level"),
            pfact("op_margin_prev", f"Operating margin, FY{fy-1}", om_p, 2, "level"),
            pfact("op_margin_chg", "Operating margin, change", om_c - om_p, 2, "change", PP),
            pfact("sga_pct_cur", f"SG&A as % of revenue, FY{fy}", sg_c, 2, "level", entity="SG&A"),
            pfact("sga_pct_prev", f"SG&A as % of revenue, FY{fy-1}", sg_p, 2, "level", entity="SG&A"),
            pfact("sga_pct_chg", "SG&A as % of revenue, change", sg_c - sg_p, 2, "change", PP, entity="SG&A"),
        ]
        movers = []
        for line, (name, al) in COSTCO_METRICS.items():
            yoy = (c[line] / b[line] - 1) * 100
            facts.append(mfact(f"{line}_cur", f"{name}, FY{fy}", c[line], "USD", "bn", 2, entity=name))
            facts.append(mfact(f"{line}_prev", f"{name}, FY{fy-1}", b[line], "USD", "bn", 2, entity=name))
            facts.append(pfact(f"{line}_yoy", f"{name}, change vs prior year", yoy, entity=name))
            facts.append(mfact(f"{line}_chg", f"{name}, change", c[line] - b[line], "USD", "bn", 2, "change", name))
            movers.append((abs(yoy), name, al, c[line] - b[line], yoy))
        movers.sort(reverse=True)
        drivers = [Driver(n, al, float(ch), float(y), i) for i, (_, n, al, ch, y) in enumerate(movers, 1)]
        sheets.append(FactSheet(
            id=f"costco_FY{fy}", domain="costco_sec",
            title=f"Costco Wholesale, FY{fy} vs FY{fy-1}",
            subject="Costco Wholesale Corporation (SEC 10-K, XBRL companyfacts)",
            period=f"FY{fy}", comparison_period=f"FY{fy-1}", comparison="year over year", currency="USD",
            facts=facts, drivers=drivers, required=[d.name for d in drivers[:2]],
            headline_key="revenue_yoy",
            period_tokens=[f"FY{fy}", f"FY{fy-1}", str(fy), str(fy - 1), f"FY{str(fy)[2:]}", f"FY{str(fy-1)[2:]}"],
            other_entities=COSTCO_OTHERS,
            notes=["Fiscal years end on the Sunday closest to 31 August."],
        ))
    return sheets


# ---- LA City General Fund: month vs same month last fiscal year ---------------
def _dept(name: str) -> str:
    small = {"And", "Of", "To", "For", "The"}
    t = " ".join(w if w in ("-",) else "-".join(p.capitalize() for p in w.split("-")) for w in name.split())
    return " ".join(w.lower() if w in small else w for w in t.split())


def _dept_aliases(name: str) -> list[str]:
    n = _dept(name).lower()
    al = [n]
    if " - " in n:
        short = n.split(" - ", 1)[1]
        if short not in ("general",):  # "general" would also match "General Fund"
            al.append(short)
    return al


def lacity_monthly_sheets() -> list[FactSheet]:
    m = pd.read_csv(INPUTS / "lacity_gf_monthly_by_department.csv")
    all_depts = sorted(_dept(x) for x in m["department_name"].unique())
    tot = m.groupby(["fiscal_year", "fiscal_month"])["amount"].sum()
    sheets = []
    for mon in range(1, 13):
        if (2025, mon) not in tot.index or (2026, mon) not in tot.index:
            continue
        cur_start = pd.Timestamp(m[(m.fiscal_year == 2026) & (m.fiscal_month == mon)]["month_start"].iloc[0])
        prev_start = cur_start - pd.DateOffset(years=1)
        lab_c, lab_p = cur_start.strftime("%B %Y"), prev_start.strftime("%B %Y")
        vc, vp = tot[(2026, mon)], tot[(2025, mon)]
        ytd_c = tot.loc[2026].loc[:mon].sum(); ytd_p = tot.loc[2025].loc[:mon].sum()
        d = (m[m.fiscal_month == mon].pivot_table(index="department_name", columns="fiscal_year",
                                                  values="amount", aggfunc="sum").fillna(0.0))
        d["chg"] = d[2026] - d[2025]
        up = d[d.chg > 0].sort_values("chg", ascending=False).head(3)
        dn = d[d.chg < 0].sort_values("chg").head(2)
        drv = pd.concat([up, dn]).assign(a=lambda x: x.chg.abs()).sort_values("a", ascending=False)
        facts = [
            mfact("total_cur", f"General Fund postings, {lab_c}", vc, "USD", "mn", 1),
            mfact("total_prev", f"General Fund postings, {lab_p}", vp, "USD", "mn", 1),
            pfact("total_yoy", "General Fund postings, change vs same month last year", (vc / vp - 1) * 100),
            mfact("total_chg", "General Fund postings, change", vc - vp, "USD", "mn", 1, "change"),
            mfact("ytd_cur", f"FY2026 year-to-date postings through {lab_c}", ytd_c, "USD", "bn", 2),
            mfact("ytd_prev", f"FY2025 year-to-date postings through {lab_p}", ytd_p, "USD", "bn", 2),
            pfact("ytd_yoy", "Year-to-date postings, change vs prior year", (ytd_c / ytd_p - 1) * 100),
        ]
        drivers = []
        for i, (name, r) in enumerate(drv.iterrows(), 1):
            nm = _dept(name)
            facts.append(mfact(f"drv{i}_chg", f"{nm}: change in postings", r.chg, "USD", "mn", 1, "change", nm))
            facts.append(mfact(f"drv{i}_cur", f"{nm}: postings, {lab_c}", r[2026], "USD", "mn", 1, entity=nm))
            facts.append(mfact(f"drv{i}_prev", f"{nm}: postings, {lab_p}", r[2025], "USD", "mn", 1, entity=nm))
            yoy = (r[2026] / r[2025] - 1) * 100 if r[2025] > 0 else None
            if yoy is not None and abs(yoy) < 1000:
                facts.append(pfact(f"drv{i}_yoy", f"{nm}: change vs same month last year", yoy, entity=nm))
            drivers.append(Driver(nm, _dept_aliases(name), float(r.chg), yoy, i))
        named = {x.name for x in drivers}
        sheets.append(FactSheet(
            id=f"lacity_gf_{cur_start:%Y-%m}", domain="lacity_gl",
            title=f"LA City General Fund postings, {lab_c} vs {lab_p}",
            subject="City of Los Angeles General Fund (Controller monthly expenditure postings)",
            period=lab_c, comparison_period=lab_p, comparison="year over year", currency="USD",
            facts=facts, drivers=drivers, required=[x.name for x in drivers[:2]],
            headline_key="total_yoy",
            period_tokens=sorted({str(cur_start.year), str(prev_start.year), "FY2026", "FY2025", "2025", "2026",
                                  "FY26", "FY25"}),
            other_entities=[x for x in all_depts if x not in named],
            notes=["Monthly postings by transaction month; fiscal year runs July to June."],
        ))
    return sheets


def lacity_bva_sheets() -> list[FactSheet]:
    b = pd.read_csv(INPUTS / "lacity_gf_budget_by_department.csv")
    all_depts = sorted(_dept(x) for x in b["department_name"].unique())
    sheets = []
    for fy in sorted(b.fiscal_year.unique()):
        x = b[b.fiscal_year == fy].copy()
        ad, rv = x.adopted_budget.sum(), x.revised_budget.sum()
        act, enc = x.actual_expense.sum(), x.encumbrance.sum()
        com = x.total_expenditures.sum()   # same basis as the source repo (actual + encumbrance as reported)
        x["com"] = x.total_expenditures
        x["util"] = x.com / x.revised_budget * 100
        x["unspent"] = x.revised_budget - x.com
        low = x[x.revised_budget > 50e6].sort_values("util").head(3)
        facts = [
            mfact("adopted", f"General Fund adopted budget, FY{fy}", ad, "USD", "bn", 2),
            mfact("revised", f"General Fund revised budget, FY{fy}", rv, "USD", "bn", 2),
            mfact("revision", "In-year budget revision (revised minus adopted)", rv - ad, "USD", "mn", 1, "change"),
            mfact("committed", "Committed spend (actual + encumbrance)", com, "USD", "bn", 2),
            mfact("actual", "Actual expenditure", act, "USD", "bn", 2),
            mfact("encumbered", "Encumbrances", enc, "USD", "mn", 1),
            pfact("utilisation", "Utilisation of revised budget", com / rv * 100, 1, "level"),
            pfact("unspent_share", "Unspent share of revised budget", (1 - com / rv) * 100, 1, "level"),
            mfact("unspent", "Unspent revised budget", rv - com, "USD", "mn", 1),
        ]
        drivers = []
        for i, (_, r) in enumerate(low.iterrows(), 1):
            nm = _dept(r.department_name)
            facts.append(pfact(f"low{i}_util", f"{nm}: utilisation of revised budget", r.util, 1, "level", entity=nm))
            facts.append(pfact(f"low{i}_unspent_share", f"{nm}: unspent share of revised budget", 100 - r.util, 1, "level", entity=nm))
            facts.append(mfact(f"low{i}_revised", f"{nm}: revised budget", r.revised_budget, "USD", "mn", 1, entity=nm))
            facts.append(mfact(f"low{i}_unspent", f"{nm}: unspent budget", r.unspent, "USD", "mn", 1, entity=nm))
            drivers.append(Driver(nm, _dept_aliases(r.department_name), float(-r.unspent), None, i))
        named = {d.name for d in drivers}
        sheets.append(FactSheet(
            id=f"lacity_bva_FY{fy}", domain="lacity_gl",
            title=f"LA City General Fund budget vs actual, FY{fy}",
            subject="City of Los Angeles General Fund (Controller budget and expenditures)",
            period=f"FY{fy}", comparison_period="revised budget", comparison="budget vs actual", currency="USD",
            facts=facts, drivers=drivers, required=[d.name for d in drivers[:2]],
            headline_key="utilisation",
            period_tokens=[f"FY{fy}", str(fy), str(fy - 1), f"FY{str(fy)[2:]}"],
            other_entities=[d for d in all_depts if d not in named],
            notes=["Lowest-utilisation departments are limited to those with a revised budget above $50m."],
        ))
    return sheets


def build_all() -> list[FactSheet]:
    return sama_sheets() + costco_sheets() + lacity_monthly_sheets() + lacity_bva_sheets()


def write_all(out: Path) -> list[FactSheet]:
    out.mkdir(parents=True, exist_ok=True)
    sheets = build_all()
    for s in sheets:
        (out / f"{s.id}.json").write_text(json.dumps(s.to_dict(), indent=2, ensure_ascii=False) + "\n")
    return sheets
