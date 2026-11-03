"""Rule-based guard for generated commentary.

A draft passes only if:
  1. every number in it matches a fact in the sheet (same unit class, consistent with the
     number of decimals written, e.g. "6.8%" matches 6.83 but not 6.9; "$15bn" matches 15.3);
  2. direction words next to a change number ("up", "fell", "a decline of") agree with the
     sign of the matched fact, and direction words after a driver name agree with that
     driver's change;
  3. years / period labels are ones in the sheet;
  4. no in-domain entity outside the sheet is named (e.g. a sector that is not a driver);
  5. no causal, macro or forward-looking claim from a blocklist appears unless the sheet
     itself contains the term;
  6. the headline change and the required drivers are all mentioned;
  7. basic format: 35-180 words, plain prose, no leaked JSON keys, no non-Latin script.

It is deliberately conservative: a false alarm costs one retry, a missed error ships.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from .facts import FactSheet, Fact, MONEY, COUNT, PCT, PP

UP = r"(?:increas\w*|ris(?:e|es|en|ing)|rose|gr[eo]w\w*|growth|up|higher|gain\w*|climb\w*|jump\w*|expan\w*|surg\w*|advanc\w*|improv\w*|accelerat\w*|boost\w*)"
DOWN = r"(?:decreas\w*|declin\w*|fell|fall\w*|drop\w*|down|lower|contract\w*|shr[aiu]nk\w*|reduc\w*|slip\w*|dip\w*|weaken\w*|slow\w*|eas(?:e|ed|ing)|softer|soften\w*|slump\w*|plung\w*)"
DIR_RE = re.compile(rf"\b(?P<up>{UP})\b|\b(?P<down>{DOWN})\b", re.I)
BOUNDARY_RE = re.compile(r"[.;:,()]|\b(?:while|whereas|but|and|with|which|although|though|as)\b", re.I)
SENT_RE = re.compile(r"(?<=[.!?])\s+")

CUR = r"(?:US\$|\$|SAR|USD|SR)"
NUM_RE = re.compile(
    rf"(?P<cur>{CUR})?\s?(?P<sign>[+\-\u2212])?\s?(?P<cur2>{CUR})?\s?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s?(?P<unit>percentage\s+points?|percent(?:age)?\s+pts?|pp\b|ppt\b|bps?\b|basis\s+points?|%|percent\b|per\s+cent\b|"
    r"bn\b|billion\b|b\b|mn\b|million\b|m\b|k\b|thousand\b))?"
    r"(?:\s?(?P<cur3>SAR|riyals?|USD|dollars?)\b)?",
    re.I,
)
PERIOD_RE = re.compile(r"\b(?:FY\s?(?P<fy>\d{2,4})|Q(?P<q>[1-4])|H[12]|(?P<yr>(?:19|20)\d{2}))\b", re.I)
SCALES = {"bn": 1e9, "billion": 1e9, "b": 1e9, "mn": 1e6, "million": 1e6, "m": 1e6, "k": 1e3, "thousand": 1e3}

CLAIMS = {
    "macro/causal": ["inflation", "pandemic", "covid", "coronavirus", "lockdown", "interest rate", "vision 2030",
                     "tourism", "tourist", "hajj", "umrah", "ramadan", "eid", "holiday", "festive", "seasonal",
                     "weather", "recession", "supply chain", "tariff", "consumer confidence", "oil price",
                     "membership fee", "e-commerce", "gasoline", "gas price", "wildfire", "layoff", "hiring",
                     "overtime", "headcount", "market share", "competitor", "competition", "economy", "economic",
                     "gdp", "vat", "price increase", "pricing", "population", "consumer sentiment", "digital payment",
                     "cashless", "mada"],
    "forward_looking": ["expect", "will continue", "is likely", "are likely", "forecast", "outlook", "guidance",
                        "next year", "next quarter", "going forward", "in the coming", "we anticipate", "poised"],
    # every sheet compares with the same period a year earlier (or adopted vs revised budget)
    "wrong_comparison_basis": ["previous quarter", "prior quarter", "last quarter", "preceding quarter",
                               "quarter-on-quarter", "quarter-over-quarter", "sequential", "previous month",
                               "prior month", "last month", "preceding month", "month-on-month", "month-over-month"],
    "interpretation": ["efficiency", "efficient", "liquidity", "commitment to", "financial position",
                       "financial health", "demand", "consumer spending habits", "resilience", "resilient"],
}


@dataclass
class Issue:
    type: str
    detail: str


@dataclass
class Report:
    passed: bool
    issues: list[Issue] = field(default_factory=list)
    numbers: list[dict] = field(default_factory=list)
    words: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def types(self) -> list[str]:
        return sorted({i.type for i in self.issues})


def _norm(text: str) -> str:
    t = text.replace("\u2212", "-").replace("\u2013", "-").replace("\u00a0", " ")
    return t


def _decimals(num: str) -> int:
    return len(num.split(".")[1]) if "." in num else 0


def _match(x: float, d: int, mult: float, f: Fact, signed: bool, neg: bool) -> bool:
    """x as written (abs value), d decimals, mult = scale written in text (None = use the fact's)."""
    if f.unit in (MONEY, COUNT):
        m = mult if mult is not None else {"bn": 1e9, "mn": 1e6, "k": 1e3, "": 1.0}[f.scale]
    else:
        m = 1.0
    target = f.value
    if signed:
        if neg != (target < 0):
            return False
    tol = 0.5 * 10 ** (-d) * m * (1 + 1e-9) + 1e-9 * abs(target)
    return abs(x * m - abs(target)) <= tol


def _dir_in(s: str):
    """Return 'up'/'down' for the last direction word in s (None if none)."""
    last = None
    for mm in DIR_RE.finditer(s):
        last = "up" if mm.group("up") else "down"
    return last


def _dir_first(s: str):
    mm = DIR_RE.search(s)
    if not mm:
        return None
    return "up" if mm.group("up") else "down"


def _alias_spans(text_l: str, aliases: list[str]):
    """Longest alias first; a shorter alias inside an already-matched span is not counted again."""
    taken: list[tuple[int, int]] = []
    for a in sorted(set(aliases), key=len, reverse=True):
        for mm in re.finditer(r"(?<![\w&])" + re.escape(a) + r"(?![\w&])", text_l):
            if any(s <= mm.start() < e for s, e in taken):
                continue
            taken.append((mm.start(), mm.end()))
            yield mm.start(), mm.end()


def validate(text: str, sheet: FactSheet) -> Report:
    raw = _norm(text).strip()
    issues: list[Issue] = []
    words = len(re.findall(r"\b\w[\w'&-]*\b", raw))

    # ---- format -------------------------------------------------------------
    if words < 35 or words > 180:
        issues.append(Issue("format", f"length {words} words (allowed 35-180)"))
    if re.search(r"\b[a-z]+_[a-z_]+\b", raw):
        issues.append(Issue("format", "leaked fact-sheet key: " + re.search(r"\b[a-z]+_[a-z_]+\b", raw).group(0)))
    if re.search(r"[\u0400-\u04ff\u0600-\u06ff\u3040-\u30ff\u4e00-\u9fff]", raw):
        issues.append(Issue("format", "non-Latin script in output"))
    if re.search(r"^\s*(?:#|\*\s|\*\*|-\s|\d+\.\s)", raw, re.M) or "**" in raw:
        issues.append(Issue("format", "markdown/list formatting"))

    # ---- period tokens (removed before number extraction) --------------------
    allowed = {t.upper().replace(" ", "") for t in sheet.period_tokens}
    body = raw
    for mm in list(PERIOD_RE.finditer(raw)):
        tok = mm.group(0).upper().replace(" ", "")
        if mm.group("fy") and len(mm.group("fy")) == 2:
            tok_alt = "FY20" + mm.group("fy")
        else:
            tok_alt = tok
        if tok not in allowed and tok_alt not in allowed:
            issues.append(Issue("unsupported_period", f"'{mm.group(0)}' is not a period in this fact sheet"))
        body = body[:mm.start()] + " " * (mm.end() - mm.start()) + body[mm.end():]

    # ---- numbers ---------------------------------------------------------------
    nums = []
    cited: set[str] = set()
    prev_end = 0
    for mm in NUM_RE.finditer(body):
        numtxt = mm.group("num")
        if not numtxt:
            continue
        x = float(numtxt.replace(",", ""))
        d = _decimals(numtxt)
        unit = (mm.group("unit") or "").lower()
        cur = (mm.group("cur") or mm.group("cur2") or mm.group("cur3") or "").upper()
        cur = {"$": "USD", "US$": "USD", "DOLLAR": "USD", "DOLLARS": "USD", "SR": "SAR",
               "RIYAL": "SAR", "RIYALS": "SAR"}.get(cur, cur)
        sign = mm.group("sign")
        neg = sign in ("-", "\u2212")
        signed = sign is not None
        if unit.startswith(("percentage point", "pp", "ppt")) or re.match(r"percent(age)?\s+pts?", unit):
            cls, mult = PP, None
        elif unit.startswith(("bp", "basis")):
            cls, mult, x, d = PP, None, x / 100, d + 2
        elif unit in ("%", "percent", "per cent"):
            cls, mult = PCT, None
        elif unit in SCALES:
            cls, mult = ("money" if cur else "scaled"), SCALES[unit]
        else:
            cls, mult = ("money" if cur else "bare"), (1.0 if cur else None)

        cands = []
        for f in sheet.facts:
            if cls == PCT and f.unit != PCT: continue
            if cls == PP and f.unit != PP: continue
            if cls == "money" and f.unit != MONEY: continue
            if cls == "scaled" and f.unit not in (MONEY, COUNT): continue
            if _match(x, d, mult, f, signed, neg):
                cands.append(f)
        # wrong unit: % written for a pp fact or vice versa
        unit_swap = []
        if not cands and cls in (PCT, PP):
            other = PP if cls == PCT else PCT
            unit_swap = [f for f in sheet.facts if f.unit == other and _match(x, d, None, f, signed, neg)]
        entry = {"text": mm.group(0).strip(), "class": cls, "matched": [f.key for f in cands]}
        nums.append(entry)
        if unit_swap:
            issues.append(Issue("unit_mismatch", f"'{entry['text']}' matches {unit_swap[0].key} but uses the wrong unit (% vs pp)"))
        elif not cands:
            issues.append(Issue("unsupported_number", f"'{entry['text']}' does not match any fact"))
        else:
            if cur and all(f.currency and f.currency != cur for f in cands):
                issues.append(Issue("wrong_currency", f"'{entry['text']}' uses {cur}, sheet is {sheet.currency}"))
            cited.update(f.key for f in cands)
            # direction check: only when every candidate is a change fact
            if all(f.kind == "change" for f in cands):
                signs = {("up" if f.value > 0 else "down") for f in cands if f.value != 0}
                left = body[prev_end:mm.start()]
                bl = list(BOUNDARY_RE.finditer(left))
                left = left[bl[-1].end():] if bl else left
                right = body[mm.end():mm.end() + 40]
                br = BOUNDARY_RE.search(right)
                right = right[:br.start()] if br else right
                right = " ".join(right.split()[:3])
                dirw = _dir_in(left) or _dir_first(right)
                if dirw and signs and dirw not in signs:
                    issues.append(Issue("wrong_direction", f"'{entry['text']}' described as {dirw} but the fact is {'/'.join(sorted(signs))}"))
        prev_end = mm.end()

    if sheet.headline_key not in cited:
        h = sheet.fact(sheet.headline_key)
        issues.append(Issue("missing_headline", f"headline figure not cited: {h.label} ({h.display})"))

    # ---- entities --------------------------------------------------------------
    low = raw.lower()
    masked = low
    for dv in sheet.drivers:
        spans = list(_alias_spans(low, dv.aliases + [dv.name.lower()]))
        if dv.name in sheet.required and not spans:
            issues.append(Issue("missing_driver", f"required driver not mentioned: {dv.name}"))
        for s0, s1 in spans:
            masked = masked[:s0] + "#" * (s1 - s0) + masked[s1:]
            if dv.change == 0 or sheet.comparison == "budget vs actual":
                continue
            seg = low[s1:]
            stop = re.search(r"\.(?!\d)|;|\b(?:while|whereas|but|and)\b", seg)
            seg = seg[:stop.start()] if stop else seg
            seg = seg.split("offset")[0]
            # "the decrease in X" / "despite the increase in X": the direction sits before the name
            lm = re.search(r"\b(increase|rise|growth|gain|decrease|decline|drop|fall|reduction)s?\s+in\s+(?:the\s+)?$",
                           low[max(0, s0 - 40):s0])
            if lm:
                dw = "up" if lm.group(1) in ("increase", "rise", "growth", "gain") else "down"
            else:
                # the first direction word after the name, ignoring words that belong to a number clause later
                dw = _dir_first(" ".join(seg.split()[:6]))
            exp = "up" if dv.change > 0 else "down"
            if dw and dw != exp:
                issues.append(Issue("wrong_direction", f"{dv.name} described as {dw} but its change is {exp}"))
    from .facts import SAMA_ALIASES
    for name in sheet.other_entities:
        al = {name.lower()} | set(SAMA_ALIASES.get(name, []))
        if " - " in name:
            al.add(name.split(" - ", 1)[1].lower())
        hit = None
        for a in al:
            if a.startswith(("other", "'other", '"other')) or a in ("miscellaneous",):
                continue
            if " " in a or "&" in a or len(a) >= 7 and a not in ("general",):
                if re.search(r"(?<![\w&#])" + re.escape(a) + r"(?![\w&#])", masked):
                    hit = a; break
        if not hit and " " not in name and name not in ("Other",):
            # single-word names: only when written capitalised (so "health" or "target" as words do not count)
            for mm in re.finditer(r"\b" + re.escape(name) + r"\b", raw):
                if masked[mm.start()] != "#":
                    hit = name; break
        if hit:
            issues.append(Issue("unsupported_entity", f"mentions '{name}', which is not in this fact sheet"))

    sheet_text = " ".join([sheet.title, sheet.subject, *sheet.notes, *(f.label for f in sheet.facts)]).lower()
    for kind, terms in CLAIMS.items():
        for t in terms:
            if t in sheet_text:
                continue
            if re.search(r"\b" + re.escape(t), low):
                issues.append(Issue("unsupported_claim", f"{kind}: '{t}'"))

    return Report(passed=not issues, issues=issues, numbers=nums, words=words)
