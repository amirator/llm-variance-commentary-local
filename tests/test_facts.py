"""Fact sheets are deterministic and tie back to the source projects' published figures."""
from vcomm.facts import build_all


def test_sheet_counts(sheets):
    doms = [s.domain for s in sheets.values()]
    assert len(sheets) == 35
    assert doms.count("sama_pos") == 16
    assert doms.count("costco_sec") == 5
    assert sum(d.startswith("lacity") for d in doms) == 14


def test_deterministic():
    a = [s.to_dict() for s in build_all()]
    b = [s.to_dict() for s in build_all()]
    assert a == b


def test_lacity_fy2026_matches_source_repo(sheets):
    s = sheets["lacity_bva_FY2026"]
    assert s.fact("revised").display == "$10.19bn"
    assert s.fact("adopted").display == "$9.56bn"
    assert s.fact("utilisation").display == "95.4%"
    assert s.fact("unspent").display == "$471.2m"


def test_costco_fy2026_revenue(sheets):
    s = sheets["costco_FY2026"]
    assert s.fact("revenue_cur").display == "$303.2bn"
    assert s.fact("revenue_yoy").display == "+10.1%"


def test_required_drivers_exist(sheets):
    for s in sheets.values():
        names = [d.name for d in s.drivers]
        assert s.required and all(r in names for r in s.required), s.id
