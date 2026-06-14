from e2e.steps.workbench import pick_ignore_candidate, should_skip_merge


def test_should_skip_merge_when_less_than_four():
    assert should_skip_merge([]) is True
    assert should_skip_merge(["c1", "c2", "c3"]) is True


def test_should_not_skip_merge_when_four_or_more():
    assert should_skip_merge(["c1", "c2", "c3", "c4"]) is False


def test_pick_ignore_candidate_skips_published_and_picks_last_available():
    candidate_ids = ["c1", "c2", "c3", "c4"]
    assert pick_ignore_candidate(candidate_ids, "c1") == "c4"
    assert pick_ignore_candidate(candidate_ids, "c4") == "c3"


def test_pick_ignore_candidate_returns_none_when_only_published_exists():
    assert pick_ignore_candidate(["c1"], "c1") is None
