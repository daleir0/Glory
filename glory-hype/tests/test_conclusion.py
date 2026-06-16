import pytest
from glory_hype.narrative.conclusion import Conclusion, parse_conclusion, unavailable


def test_parse_clean_json():
    raw = ('{"bias":"bullish","confidence":0.8,'
           '"key_drivers":["ETF inflows"],"caution_flags":["overheated"],'
           '"source_breakdown":{"news":2,"onchain":1}}')
    c = parse_conclusion(raw, based_on=["h1"], generated_at=1000)
    assert c.bias == "bullish"
    assert c.confidence == 0.8
    assert c.score == 80          # +round(0.8*100) * sign(+1) -> 80
    assert c.based_on == ["h1"]


def test_parse_json_in_markdown_fence():
    raw = "Here is my answer:\n```json\n{\"bias\":\"bearish\",\"confidence\":0.5}\n```\n"
    c = parse_conclusion(raw, based_on=[], generated_at=1)
    assert c.bias == "bearish"
    assert c.score == -50


def test_neutral_zero_score():
    c = parse_conclusion('{"bias":"neutral","confidence":0.9}', based_on=[], generated_at=1)
    assert c.score == 0


def test_parse_garbage_returns_unavailable():
    c = parse_conclusion("not json at all", based_on=[], generated_at=5)
    assert c.bias == "neutral"
    assert c.confidence == 0.0
    assert "synthesis unavailable" in " ".join(c.caution_flags).lower()


def test_unavailable_factory():
    c = unavailable(generated_at=7)
    assert c.confidence == 0.0
    assert c.to_dict()["generated_at"] == 7


def test_confidence_clamped_to_one():
    c = parse_conclusion('{"bias":"bullish","confidence":1.5}', based_on=[], generated_at=1)
    assert c.confidence == 1.0
    assert c.score == 100


def test_json_with_trailing_prose_braces():
    raw = '{"bias":"bearish","confidence":0.4} ...note: see {example}'
    c = parse_conclusion(raw, based_on=[], generated_at=1)
    assert c.bias == "bearish"
    assert c.score == -40
