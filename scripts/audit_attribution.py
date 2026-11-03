"""Attribution audit for drafts that PASSED the validator.

The validator checks that every number exists somewhere in the fact sheet. It does not
check that the number is attached to the right line item. This script is a rough
heuristic for that gap: for each cited number it finds the closest driver mentioned
earlier in the same sentence and flags the number when none of the facts it matched
belongs to that driver (or when a driver-only number appears with no driver in front).
Flags are leads for manual review, not verdicts.
"""
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def audit(stem: str):
    rows = []
    for f in sorted(glob.glob(str(ROOT / "outputs" / stem / "*.json"))):
        r = json.load(open(f))
        if r["source"] != "llm":
            continue
        sheet = json.load(open(ROOT / "data" / "factsheets" / f"{r['sheet_id']}.json"))
        ent = {x["key"]: x["entity"] for x in sheet["facts"]}
        text = r["final_text"]
        low = text.lower()
        mentions = []
        for d in sheet["drivers"]:
            for a in d["aliases"]:
                for m in re.finditer(r"(?<![\w&])" + re.escape(a) + r"(?![\w&])", low):
                    mentions.append((m.start(), m.end(), d["name"]))
        pos = 0
        for n in r["final_report"]["numbers"]:
            i = text.find(n["text"], pos)
            if i < 0:
                continue
            pos = i + len(n["text"])
            sent_start = max(text.rfind(". ", 0, i), 0)
            before = [m for m in mentions if sent_start <= m[1] <= i]
            near = max(before, key=lambda m: m[1])[2] if before else None
            matched = {ent.get(k) for k in n["matched"]}
            if near is not None and near not in matched:
                rows.append((r["sheet_id"], n["text"], near, sorted(map(str, matched))))
            elif near is None and None not in matched:
                rows.append((r["sheet_id"], n["text"], "(no driver named before it)", sorted(map(str, matched))))
    return rows


if __name__ == "__main__":
    stems = sys.argv[1:] or ["qwen2.5-1.5b-instruct-q4_k_m", "qwen2.5-0.5b-instruct-q4_k_m"]
    for s in stems:
        rows = audit(s)
        print(f"## {s}: {len(rows)} flagged numbers")
        for row in rows:
            print(" | ".join(map(str, row)))
