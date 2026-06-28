from src.services.knowledge.writing_technique_field_utils import (
    clamp_confidence,
    coerce_usage_mode,
    truncate_technique_field,
)


def test_truncate_technique_field():
    assert truncate_technique_field("a" * 50, max_len=30) == "a" * 30
    assert truncate_technique_field(None, max_len=30) is None


def test_clamp_confidence():
    assert clamp_confidence(-5) == 0
    assert clamp_confidence(150) == 100
    assert clamp_confidence(72) == 72


def test_coerce_usage_mode():
    assert coerce_usage_mode("DIRECT") == "DIRECT"
    assert coerce_usage_mode("bogus") == "REFERENCE"
