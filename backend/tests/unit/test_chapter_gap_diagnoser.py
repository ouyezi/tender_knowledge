from uuid import uuid4

from src.services.retrieval.chapter_gap_diagnoser import ChapterGapDiagnoser


def test_diagnose_missing_chapters_with_default_threshold():
    matched_pattern_id = uuid4()
    missing_pattern_id = uuid4()
    diagnoser = ChapterGapDiagnoser()

    result = diagnoser.diagnose(
        matched_pattern_ids=[matched_pattern_id],
        candidate_patterns=[
            {
                "pattern_id": matched_pattern_id,
                "pattern_name": "技术方案",
                "frequency": 8,
            },
            {
                "pattern_id": missing_pattern_id,
                "pattern_name": "售后服务",
                "frequency": 6,
            },
        ],
    )

    assert len(result) == 1
    assert result[0]["pattern_id"] == str(missing_pattern_id)
    assert "高频章节未覆盖" in result[0]["reason"]


def test_diagnose_respects_ratio_and_frequency_threshold():
    diagnoser = ChapterGapDiagnoser({"min_frequency": 5, "min_ratio": 0.5})

    result = diagnoser.diagnose(
        matched_pattern_ids=[],
        candidate_patterns=[
            {
                "pattern_id": uuid4(),
                "pattern_name": "低频章节",
                "frequency": 3,
            },
            {
                "pattern_id": uuid4(),
                "pattern_name": "临界章节",
                "frequency": 4,
            },
        ],
    )

    assert result == []
