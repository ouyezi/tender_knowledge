import pytest

from src.services.category_tree import assert_no_cycle, build_path


def test_build_path_root():
    assert build_path(None, "uuid-1") == "/uuid-1/"


def test_build_path_child():
    assert build_path("/parent/", "child") == "/parent/child/"


def test_assert_no_cycle_raises():
    with pytest.raises(ValueError, match="CYCLE_DETECTED"):
        assert_no_cycle("/parent/child/", "parent")


def test_assert_no_cycle_ok():
    assert_no_cycle("/parent/", "child")
