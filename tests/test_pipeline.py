"""Retry and fallback paths, driven by a stub generator (no model needed)."""
from vcomm.evaluate import stress_test
from vcomm.generate import StubGenerator
from vcomm.pipeline import draft
from vcomm.template import template_commentary


def test_first_attempt_pass(sheets):
    s = sheets["costco_FY2025"]
    o = draft(s, StubGenerator({s.id: s}))
    assert o.source == "llm" and len(o.attempts) == 1 and o.passed_first


def test_retry_then_pass(sheets):
    s = sheets["costco_FY2025"]
    bad = template_commentary(s).replace("up", "down", 1)
    gen = StubGenerator({s.id: s}, {s.id: [bad, "{template}"]})
    o = draft(s, gen)
    assert o.source == "llm" and len(o.attempts) == 2
    assert not o.attempts[0]["passed"] and o.attempts[1]["passed"]


def test_feedback_reaches_retry_prompt(sheets):
    s = sheets["lacity_gf_2025-11"]
    seen = []

    class Spy(StubGenerator):
        def __call__(self, messages, seed):
            seen.append(messages[-1]["content"])
            return super().__call__(messages, seed)

    bad = template_commentary(s) + " Inflation explains this."
    draft(s, Spy({s.id: s}, {s.id: [bad, "{template}"]}))
    assert "rejected" not in seen[0] and "inflation" in seen[1].lower()


def test_fallback_after_three_failures(sheets):
    s = sheets["sama_pos_2022Q1"]
    bad = "Spending went up a lot this quarter thanks to tourism and Ramadan."
    o = draft(s, StubGenerator({s.id: s}, {s.id: [bad] * 3}))
    assert o.source == "template" and len(o.attempts) == 3
    assert o.final_text == template_commentary(s) and o.final_report["passed"]


def test_stress_test_on_templates(sheets):
    texts = [(k, template_commentary(s)) for k, s in sheets.items()]
    res = stress_test(sheets, texts)
    for kind in ("hallucinated_number", "flipped_direction", "unsupported_entity", "unsupported_claim"):
        assert res[kind]["cases"] > 0 and res[kind]["rate"] >= 0.9, (kind, res[kind])
