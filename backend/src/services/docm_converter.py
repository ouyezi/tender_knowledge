from __future__ import annotations

import logging
import re
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

_MACRO_PART_PREFIXES = ("word/vba", "word/activeX/")
_MACRO_PART_NAMES = {
    "word/vbaProject.bin",
    "word/vbaData.xml",
    "word/vbaProjectSignature.bin",
    "word/vbaProjectSignatureAgile.bin",
}
_VBA_REL_TYPE = "relationships/vbaProject"
_MACRO_MAIN_CONTENT_TYPE = "application/vnd.ms-word.document.macroEnabled.main+xml"
_DOCX_MAIN_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)


def _is_macro_part(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if normalized in _MACRO_PART_NAMES:
        return True
    return any(normalized.startswith(prefix) for prefix in _MACRO_PART_PREFIXES)


def _scrub_content_types(xml_text: str) -> str:
    xml_text = re.sub(
        r'\s*<Override[^>]+vbaProject[^>]*/>\s*',
        "",
        xml_text,
        flags=re.IGNORECASE,
    )
    return xml_text.replace(_MACRO_MAIN_CONTENT_TYPE, _DOCX_MAIN_CONTENT_TYPE)


def _scrub_document_rels(xml_text: str) -> str:
    return re.sub(
        rf'\s*<Relationship[^>]+{_VBA_REL_TYPE}[^>]*/>\s*',
        "",
        xml_text,
        flags=re.IGNORECASE,
    )


def convert_docm_to_docx(source: Path, destination: Path) -> Path:
    """Strip macro parts from a .docm OPC package and write a .docx file."""
    if source.suffix.lower() != ".docm":
        raise ValueError(f"expected .docm file, got {source.name}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    removed_parts: list[str] = []

    with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            name = item.filename.replace("\\", "/")
            if _is_macro_part(name):
                removed_parts.append(name)
                continue

            data = zin.read(item.filename)
            if name == "[Content_Types].xml":
                data = _scrub_content_types(data.decode("utf-8")).encode("utf-8")
            elif name == "word/_rels/document.xml.rels":
                data = _scrub_document_rels(data.decode("utf-8")).encode("utf-8")

            zout.writestr(item, data)

    logger.info(
        "docm_converter converted %s -> %s removed_macro_parts=%d",
        source,
        destination,
        len(removed_parts),
    )
    return destination


def _converted_docx_is_valid(docx_path: Path) -> bool:
    try:
        with zipfile.ZipFile(docx_path, "r") as zf:
            content_types = zf.read("[Content_Types].xml").decode("utf-8")
        return "macroEnabled" not in content_types
    except Exception:
        return False


def ensure_docx_for_parse(source_path: Path) -> Path:
    """Return a .docx path suitable for python-docx; convert .docm in-place cache."""
    if source_path.suffix.lower() != ".docm":
        return source_path

    cache_path = source_path.with_name(f"{source_path.stem}.converted.docx")
    if (
        cache_path.exists()
        and cache_path.stat().st_mtime >= source_path.stat().st_mtime
        and _converted_docx_is_valid(cache_path)
    ):
        logger.info("docm_converter cache hit path=%s", cache_path)
        return cache_path

    if cache_path.exists():
        logger.warning("docm_converter invalid cache, regenerating path=%s", cache_path)
        cache_path.unlink(missing_ok=True)

    logger.info("docm_converter converting docm path=%s", source_path)
    return convert_docm_to_docx(source_path, cache_path)
