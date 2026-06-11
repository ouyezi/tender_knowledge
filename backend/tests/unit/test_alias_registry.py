from src.services.alias_registry import filter_extra_names, normalize


def test_normalize_strips_and_casefolds():
    assert normalize("  员工餐补  ") == "员工餐补"
    assert normalize("Meal Benefit") == "meal benefit"


def test_filter_extra_names_drops_canonical_duplicate():
    result = filter_extra_names("资质", ["资质", "公司资质", "资质"])
    assert result == ["公司资质"]
