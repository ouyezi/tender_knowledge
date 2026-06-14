#!/usr/bin/env python3
"""Generate sample-chinese-outline.docx fixture for hierarchy inference tests."""

from pathlib import Path

from docx import Document

OUT = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "sample-chinese-outline.docx"


def main() -> None:
    doc = Document()
    for text in [
        "第一章 项目概述",
        "概述正文。",
        "一、建设目标",
        "目标正文。",
        "### 技术架构",
        "架构正文。",
    ]:
        doc.add_paragraph(text, style="Normal")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
