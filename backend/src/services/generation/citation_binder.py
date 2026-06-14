from __future__ import annotations

import re

from src.schemas.generation import SourceCatalogEntry


class CitationBinder:
    def bind(
        self,
        *,
        llm_paragraphs: list[dict],
        catalog: list[SourceCatalogEntry],
        resolved_variables: dict[str, str],
    ) -> list[dict]:
        catalog_by_ref = {item.ref_id: item for item in catalog}
        fallback_ref = self._pick_fallback_ref(catalog)
        bound_paragraphs: list[dict] = []
        for idx, paragraph in enumerate(llm_paragraphs):
            raw_text = str(paragraph.get("text") or "").strip()
            text = self._replace_variables(raw_text, resolved_variables)
            raw_refs = [str(ref) for ref in paragraph.get("source_ref_ids") or []]
            known_refs = [ref for ref in raw_refs if ref in catalog_by_ref]
            if not known_refs and fallback_ref is not None:
                known_refs = [fallback_ref]

            for key in resolved_variables:
                var_ref_id = f"VAR-{key}"
                if var_ref_id in catalog_by_ref and var_ref_id not in known_refs and resolved_variables[key] in text:
                    known_refs.append(var_ref_id)

            citations = []
            for ref_id in known_refs:
                entry = catalog_by_ref[ref_id]
                citations.append(
                    {
                        "source_type": entry.type,
                        "source_id": entry.object_id or entry.ref_id,
                        "source_label": entry.title,
                        "excerpt": entry.excerpt,
                        "ref_id": entry.ref_id,
                    }
                )
            bound_paragraphs.append(
                {
                    "paragraph_index": idx,
                    "text": text,
                    "citations": citations,
                }
            )
        return bound_paragraphs

    @staticmethod
    def _replace_variables(text: str, resolved_variables: dict[str, str]) -> str:
        result = text
        for key, value in resolved_variables.items():
            pattern = re.compile(r"\{\{\s*" + re.escape(key) + r"\s*\}\}")
            result = pattern.sub(value, result)
        return result

    @staticmethod
    def _pick_fallback_ref(catalog: list[SourceCatalogEntry]) -> str | None:
        for prefix in ("TREQ-SP-", "TREQ-RC-"):
            for item in catalog:
                if item.ref_id.startswith(prefix):
                    return item.ref_id
        if catalog:
            return catalog[0].ref_id
        return None
