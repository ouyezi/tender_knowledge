from src.services.docx_toc_extractor import ExtractStrategy, TocEntry
from src.services.outline_heading_filter import filter_outline_entries


def _entry(title: str, level: int = 1, temp_id: str = "n1", parent: str | None = None, sort_order: int = 0):
    return TocEntry(
        temp_id=temp_id,
        parent_temp_id=parent,
        title=title,
        level=level,
        sort_order=sort_order,
    )


def test_toc_strategy_keeps_all_entries():
    entries = [_entry("一、总则"), _entry("1. 很长的正文承诺" * 5, temp_id="n2", sort_order=1)]
    result = filter_outline_entries(entries, blocks=[], strategy=ExtractStrategy.toc)
    assert len(result.kept) == 2
    assert result.stats.excluded == 0


def test_date_line_excluded():
    entries = [_entry("2026 年 5 月 19 日")]
    result = filter_outline_entries(entries, blocks=[], strategy=ExtractStrategy.content_heuristic)
    assert len(result.kept) == 0
    assert result.decisions[0].reason_code == "date_line"


def test_body_list_item_under_parent_keyword_excluded():
    parent = _entry("二、参选响应函", temp_id="n1", sort_order=0)
    child = _entry(
        "1. 根据贵方采购文件要求，我方郑重承诺将按比选文件全部要求履行合同责任和义务，"
        "并保证所提供的服务完全符合比选文件规定的全部技术标准和商务条款要求，"
        "如有违反愿承担相应法律责任。",
        level=1,
        temp_id="n2",
        parent="n1",
        sort_order=1,
    )
    result = filter_outline_entries(
        [parent, child],
        blocks=[],
        strategy=ExtractStrategy.content_heuristic,
    )
    assert len(result.kept) == 1
    assert result.kept[0].title == "二、参选响应函"
    excluded = [d for d in result.decisions if d.action == "exclude"]
    assert excluded and excluded[0].reason_code in {"body_list_item", "body_paragraph"}


def test_genuine_chapter_kept():
    entries = [
        _entry("一、报价表格式", sort_order=0),
        _entry("二、参选响应函", temp_id="n2", sort_order=1),
    ]
    result = filter_outline_entries(entries, blocks=[], strategy=ExtractStrategy.content_heuristic)
    assert len(result.kept) == 2
