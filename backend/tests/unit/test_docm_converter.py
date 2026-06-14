import zipfile
from pathlib import Path

from src.services.docm_converter import convert_docm_to_docx, ensure_docx_for_parse

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.ms-word.document.macroEnabled.main+xml"/>
  <Override PartName="/word/vbaProject.bin" ContentType="application/vnd.ms-office.vbaProject"/>
</Types>
"""

_DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/>
</Relationships>
"""

_DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>hello</w:t></w:r></w:p></w:body>
</w:document>
"""


def _write_minimal_docm(path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("word/_rels/document.xml.rels", _DOCUMENT_RELS)
        zf.writestr("word/document.xml", _DOCUMENT_XML)
        zf.writestr("word/vbaProject.bin", b"fake-macro-binary")


def test_convert_docm_to_docx_removes_macro_parts(tmp_path: Path) -> None:
    docm = tmp_path / "sample.docm"
    docx = tmp_path / "sample.docx"
    _write_minimal_docm(docm)

    convert_docm_to_docx(docm, docx)

    assert docx.exists()
    with zipfile.ZipFile(docx, "r") as zf:
        names = set(zf.namelist())
        content_types = zf.read("[Content_Types].xml").decode("utf-8")
        rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
    assert "word/vbaProject.bin" not in names
    assert "word/document.xml" in names
    assert "vbaProject" not in content_types
    assert "vbaProject" not in rels
    assert "macroEnabled" not in content_types
    assert "wordprocessingml.document.main+xml" in content_types


def test_ensure_docx_for_parse_uses_cache(tmp_path: Path) -> None:
    docm = tmp_path / "cached.docm"
    _write_minimal_docm(docm)

    first = ensure_docx_for_parse(docm)
    second = ensure_docx_for_parse(docm)

    assert first == second
    assert first.name == "cached.converted.docx"
