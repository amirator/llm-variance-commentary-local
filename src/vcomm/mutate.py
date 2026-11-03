"""Synthetic corruptions used to measure how often the validator catches known errors."""
from __future__ import annotations

import re

from .facts import FactSheet
from .validate import NUM_RE, PERIOD_RE

FLIP = {"increased": "decreased", "decreased": "increased", "rose": "fell", "fell": "rose", "up": "down",
        "down": "up", "grew": "declined", "declined": "grew", "increase": "decrease", "decrease": "increase",
        "higher": "lower", "lower": "higher", "growth": "decline", "decline": "growth", "rise": "fall",
        "fall": "rise", "gained": "lost", "dropped": "rose", "climbed": "fell"}


def _number_spans(text: str):
    masked = text
    for m in PERIOD_RE.finditer(text):
        masked = masked[:m.start()] + " " * (m.end() - m.start()) + masked[m.end():]
    return [(m.start("num"), m.end("num")) for m in NUM_RE.finditer(masked) if m.group("num")]


def perturb_number(text: str, k: int = 0) -> str | None:
    """Scale the k-th number by 1.3 (keeping its decimals), i.e. a plausible but wrong figure."""
    sp = _number_spans(text)
    if not sp:
        return None
    s, e = sp[k % len(sp)]
    num = text[s:e].replace(",", "")
    d = len(num.split(".")[1]) if "." in num else 0
    v = float(num) * 1.3 + (10 ** -d if d else 1)
    return text[:s] + f"{v:,.{d}f}" + text[e:]


def flip_direction(text: str, sheet: FactSheet) -> str | None:
    """Flip the first direction word that sits before a change figure."""
    for m in re.finditer(r"\b(" + "|".join(FLIP) + r")\b", text):
        w = m.group(1)
        return text[:m.start()] + FLIP[w] + text[m.end():]
    return None


def inject_entity(text: str, sheet: FactSheet) -> str | None:
    if not sheet.other_entities:
        return None
    pick = [e for e in sheet.other_entities if e != "Other"]
    name = pick[len(text) % len(pick)]
    return text.rstrip() + f" {name} also contributed to the change."


def inject_claim(text: str, sheet: FactSheet) -> str | None:
    claims = ["This was mainly driven by inflation.", "We expect this trend to continue next year.",
              "Seasonal holiday demand explains most of the movement."]
    return text.rstrip() + " " + claims[len(text) % len(claims)]


def drop_driver(text: str, sheet: FactSheet) -> str | None:
    d = sheet.drivers[0]
    sents = re.split(r"(?<=[.!?])\s+", text)
    keep = [s for s in sents if not any(a in s.lower() for a in d.aliases + [d.name.lower()])]
    if len(keep) == len(sents):
        return None
    return " ".join(keep)


MUTATIONS = {
    "hallucinated_number": lambda t, s: perturb_number(t, len(t)),
    "flipped_direction": flip_direction,
    "unsupported_entity": inject_entity,
    "unsupported_claim": inject_claim,
    "dropped_required_driver": drop_driver,
}
