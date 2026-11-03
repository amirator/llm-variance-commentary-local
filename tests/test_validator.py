"""Validator: clean text passes, each kind of error is caught."""
import pytest

from vcomm.template import template_commentary
from vcomm.validate import validate

SAMA = "sama_pos_2024Q3"
GOOD_SAMA = ("Average weekly point-of-sale spending in Saudi Arabia was SAR 12.76 bn in Q3 2024, up 8.4% from "
             "SAR 11.77 bn in Q3 2023. Transactions rose 14.6% to 202.4 million a week. The biggest increases "
             "came from Miscellaneous Goods and Services (up SAR 242 mn) and Other (up SAR 221 mn).")


def types(text, sheet):
    return validate(text, sheet).types


def test_template_passes_every_sheet(sheets):
    for s in sheets.values():
        rep = validate(template_commentary(s), s)
        assert rep.passed, (s.id, [i.detail for i in rep.issues])


def test_good_handwritten_text_passes(sheets):
    rep = validate(GOOD_SAMA, sheets[SAMA])
    assert rep.passed, [i.detail for i in rep.issues]


def test_rounding_is_tolerated(sheets):
    # 12.76 bn written as 12.8 bn is a fair rounding, not a new number
    assert validate(GOOD_SAMA.replace("SAR 12.76 bn", "SAR 12.8 bn"), sheets[SAMA]).passed


@pytest.mark.parametrize("old,new,kind", [
    ("up 8.4%", "up 9.4%", "unsupported_number"),              # wrong figure
    ("14.6%", "41.6%", "unsupported_number"),                   # transposed digits
    ("up 8.4%", "down 8.4%", "wrong_direction"),                # flipped sign
    ("Transactions rose", "Transactions fell", "wrong_direction"),
    ("up 8.4%", "up 8.4 pp", "unit_mismatch"),                  # % vs percentage points
    ("SAR 12.76 bn", "$12.76 bn", "wrong_currency"),
    ("in Q3 2024", "in Q4 2024", "unsupported_period"),
    ("(up SAR 221 mn)", "(up SAR 221 mn), while Hotels were flat", "unsupported_entity"),
])
def test_adversarial_edits_are_caught(sheets, old, new, kind):
    assert old in GOOD_SAMA
    assert kind in types(GOOD_SAMA.replace(old, new), sheets[SAMA])


@pytest.mark.parametrize("extra,kind", [
    (" Inflation drove most of the growth.", "unsupported_claim"),
    (" We expect the trend to continue next year.", "unsupported_claim"),
    (" Spending was up on the previous quarter.", "unsupported_claim"),
    (" This shows strong consumer demand.", "unsupported_claim"),
])
def test_unsupported_claims(sheets, extra, kind):
    assert kind in types(GOOD_SAMA + extra, sheets[SAMA])


def test_missing_required_driver(sheets):
    text = GOOD_SAMA.replace(" and Other (up SAR 221 mn)", "")
    assert "missing_driver" in types(text, sheets[SAMA])


def test_missing_headline(sheets):
    text = GOOD_SAMA.replace(", up 8.4% from SAR 11.77 bn in Q3 2023", "")
    assert "missing_headline" in types(text, sheets[SAMA])


@pytest.mark.parametrize("text", [
    "**Commentary**\n" + GOOD_SAMA,
    "- " + GOOD_SAMA,
    "Spending rose.",                                           # too short
    GOOD_SAMA + " total_value_yoy",                              # leaked fact key
])
def test_format_rules(sheets, text):
    assert "format" in types(text, sheets[SAMA])


def test_costco_unit_swap(sheets):
    s = sheets["costco_FY2026"]
    good = template_commentary(s)
    assert validate(good, s).passed
    assert "unit_mismatch" in types(good.replace("up 0.08 pp", "up 0.08%"), s)


def test_lacity_derived_number_rejected(sheets):
    s = sheets["lacity_bva_FY2026"]
    good = template_commentary(s)
    # 10.19 - 9.56 = 0.63bn is arithmetic the model was told not to do; the sheet states +$628.1m
    bad = good.replace("leaving $471.2m unspent", "leaving $471.2m unspent and a $0.71bn revision")
    assert "unsupported_number" in types(bad, s)


@pytest.mark.xfail(strict=True, reason="known limitation: entity check only knows names from the source data")
def test_entity_outside_lexicon_is_not_caught(sheets):
    assert "unsupported_entity" in types(GOOD_SAMA + " Fuel was flat.", sheets[SAMA])


def test_direction_word_before_the_name(sheets):
    s = sheets["costco_FY2022"]
    base = template_commentary(s)
    ok = base + " Despite the decrease in operating cash flow, the increase in net income was larger."
    bad = base + " Despite the increase in operating cash flow, net income was higher."
    assert "wrong_direction" not in types(ok, s)
    assert "wrong_direction" in types(bad, s)


def test_general_fund_is_not_a_department(sheets):
    s = sheets["lacity_gf_2025-08"]
    rep = validate(template_commentary(s).replace("General Fund postings", "General Fund postings overall"), s)
    assert rep.passed, [i.detail for i in rep.issues]


def test_decimal_point_does_not_end_the_clause(sheets):
    # found in the 0.5B run: "$88.1m" used to cut the clause at the decimal point
    s = sheets["lacity_gf_2026-02"]
    bad = template_commentary(s) + " Non-Departmental - General posted a $11.3m increase."
    assert "wrong_direction" in types(bad, s)
