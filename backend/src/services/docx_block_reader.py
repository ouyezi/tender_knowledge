from __future__ import annotations

from collections.abc import Iterator

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


def sanitize_block_text(text: str) -> str:
    return text.replace("\x00", "")


def iter_document_blocks(doc: DocxDocument) -> Iterator[tuple[str, Paragraph | Table | object]]:
    body = doc.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield "paragraph", Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield "table", Table(child, doc)
        else:
            yield "other", child


def table_text(table: Table) -> str:
    lines: list[str] = []
    for row in table.rows:
        cells = [(cell.text or "").strip() for cell in row.cells]
        cells = [cell for cell in cells if cell]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def paragraph_has_image(paragraph: Paragraph) -> bool:
    return bool(paragraph._p.xpath(".//w:drawing"))


def open_docx(path) -> DocxDocument:
    return Document(str(path))
