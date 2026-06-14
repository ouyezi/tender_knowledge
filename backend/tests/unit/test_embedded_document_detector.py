from src.services.docx_content_collector import RawBlock
from src.services.embedded_document_detector import (
    is_embedded_document_start,
    is_main_outline_resume,
    is_vendor_subsection_resume,
)
from src.services.heading_level_detector import detect_heading_level


def _block(index: int, text: str, style_name: str | None = "Normal") -> RawBlock:
    return RawBlock(index=index, block_type="paragraph", text=text, style_name=style_name, has_image=False)


def test_embedded_start_requires_chapter_one_on_normal_style():
    detection = detect_heading_level("第一章 总则", "Normal")
    assert detection is not None
    assert is_embedded_document_start(
        _block(1, "第一章 总则"),
        detection,
        max_open_level=4,
    )


def test_embedded_start_after_chinese_list_context():
    detection = detect_heading_level("第一章 总则", "Normal")
    assert is_embedded_document_start(
        _block(2004, "第一章 总则"),
        detection,
        max_open_level=7,
    )


def test_embedded_start_rejects_shallow_outline():
    detection = detect_heading_level("第一章 总则", "Normal")
    assert is_embedded_document_start(
        _block(1, "第一章 总则"),
        detection,
        max_open_level=1,
    ) is False


def test_embedded_start_rejects_heading_style_chapter():
    detection = detect_heading_level("第一章 总则", "Heading 1")
    assert is_embedded_document_start(
        _block(1, "第一章 总则", "Heading 1"),
        detection,
        max_open_level=4,
    ) is False


def test_main_resume_requires_heading_style_numeric():
    detection = detect_heading_level("6.3服务持续保障方案", "Heading 3")
    assert is_main_outline_resume(
        _block(10, "6.3服务持续保障方案", "Heading 3"),
        detection,
        embedded_active=True,
    )


def test_main_resume_rejects_embedded_numeric():
    detection = detect_heading_level("6.3 外部审计", "Normal (Web)")
    assert is_main_outline_resume(
        _block(10, "6.3 外部审计", "Normal (Web)"),
        detection,
        embedded_active=True,
    ) is False


def test_vendor_subsection_resume_exits_embedded_island():
    detection = detect_heading_level("三、合作方美团外卖的应急预案", "Normal")
    assert is_vendor_subsection_resume(
        _block(2039, "三、合作方美团外卖的应急预案"),
        detection,
        embedded_active=True,
    )
