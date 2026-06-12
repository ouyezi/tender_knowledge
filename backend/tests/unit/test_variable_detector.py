from src.services.variable_detector import detect_variables


def test_detect_variables_unique_by_first_seen_order():
    text = "报价为{{price}}元，税率{{tax_rate}}，再次出现{{price}}"
    assert detect_variables(text) == ["price", "tax_rate"]


def test_detect_variables_ignores_invalid_placeholders():
    text = "{{ valid_key }} {{}} {{ invalid key }} {price} {{_ok2}}"
    assert detect_variables(text) == ["valid_key", "_ok2"]
