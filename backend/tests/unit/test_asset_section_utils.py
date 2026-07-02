from uuid import uuid4

from src.models.chunk_asset import ChunkAsset
from src.services.knowledge.asset_section_utils import (
    asset_char_range_within_section,
    asset_visible_in_section,
    filter_assets_for_section,
)


def _asset(**kwargs) -> ChunkAsset:
  defaults = {
      "kb_id": uuid4(),
      "doc_id": uuid4(),
      "asset_type": "table",
      "char_start": 10,
      "char_end": 20,
  }
  defaults.update(kwargs)
  return ChunkAsset(**defaults)


def test_asset_char_range_within_section_requires_start_and_end_inside_bounds():
    asset = _asset(char_start=10, char_end=20)
    assert asset_char_range_within_section(asset, char_start=5, char_end=25)
    assert not asset_char_range_within_section(asset, char_start=15, char_end=25)
    assert not asset_char_range_within_section(asset, char_start=5, char_end=15)


def test_asset_char_range_rejects_asset_extending_far_beyond_section():
    asset = _asset(char_start=6814, char_end=200845)
    assert not asset_char_range_within_section(asset, char_start=6776, char_end=6915)


def test_asset_visible_in_section_table_header_must_appear_in_section():
    section = "## 法人代表身份证明\n\n| 法人代表身份证明 | 内容 |"
    visible = _asset(
        asset_type="table",
        raw_markdown="| 指标 | 2019 |\n| --- | --- |\n| 净资产 | 1% |",
    )
    hidden = _asset(
        asset_type="table",
        raw_markdown="| 法人代表身份证明 | 内容 |\n| --- | --- |",
    )
    assert not asset_visible_in_section(visible, section)
    assert asset_visible_in_section(hidden, section)


def test_filter_assets_for_section_drops_non_visible_table_assets():
    section = "section text only"
    assets = [
        _asset(asset_type="table", raw_markdown="| 指标 | 2019 |"),
        _asset(asset_type="image", raw_markdown="![img](images/a.png)"),
    ]
    filtered = filter_assets_for_section(assets, section)
    assert len(filtered) == 1
    assert filtered[0].asset_type == "image"


def test_asset_visible_in_section_table_skipped_when_already_inline():
    table = (
        "| 员工痛点 | 消费场景少 |\n"
        "| --- | --- |\n"
        "| 使用体感差 | 无新意 |"
    )
    section = f"## 2.1 痛点\n\n{table}\n"
    asset = _asset(asset_type="table", raw_markdown=table)
    assert not asset_visible_in_section(asset, section)


def test_filter_assets_for_section_deduplicates_same_table_assets():
    table = "| 员工痛点 | 消费场景少 |\n| --- | --- |"
    section = f"## 2.1\n\n{table}\n"
    assets = [
        _asset(id=1, asset_type="table", raw_markdown=table, char_start=10, char_end=50),
        _asset(id=2, asset_type="table", raw_markdown=table, char_start=10, char_end=50),
    ]
    assert filter_assets_for_section(assets, section) == []


def test_asset_visible_in_section_table_skipped_when_table_ref_placeholder_present():
    section = "## 章节\n\n<!-- table-ref:tables/t0000.json -->\n|列A|列B|\n"
    asset = _asset(
        asset_type="table",
        raw_markdown="|列A|列B|\n|---|---|\n|1|2|",
        table_schema={"table_ref": "tables/t0000.json"},
    )
    assert not asset_visible_in_section(asset, section)
