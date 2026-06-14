from __future__ import annotations

from src.schemas.generation import ManualAssetComplianceEntry, ResolvedGenerationContext


class ComplianceChecker:
    def apply(
        self,
        *,
        resolved: ResolvedGenerationContext,
        manual_asset_compliance: list[ManualAssetComplianceEntry] | list[dict],
    ) -> tuple[ResolvedGenerationContext, list[dict]]:
        compliance_map: dict[str, ManualAssetComplianceEntry] = {}
        for item in manual_asset_compliance:
            entry = item if isinstance(item, ManualAssetComplianceEntry) else ManualAssetComplianceEntry(**item)
            compliance_map[str(entry.manual_asset_id)] = entry

        removed_ref_ids: set[str] = set()
        missing_material_hints: list[dict] = []
        filtered_catalog = []
        for entry in resolved.source_catalog:
            if entry.type != "manual_asset":
                filtered_catalog.append(entry)
                continue
            compliance = compliance_map.get(str(entry.object_id))
            if compliance is None or compliance.status == "pass":
                filtered_catalog.append(entry)
                continue
            removed_ref_ids.add(entry.ref_id)
            if compliance.status in {"missing", "fail"}:
                missing_material_hints.append(
                    {
                        "manual_asset_id": str(compliance.manual_asset_id),
                        "message": compliance.message or "manual asset compliance check failed",
                        "status": compliance.status,
                    }
                )

        filtered_layers = dict(resolved.layers)
        l5_items = []
        for line in filtered_layers.get("knowledge_pack", []):
            if not any(f"[{ref_id}]" in line for ref_id in removed_ref_ids):
                l5_items.append(line)
        filtered_layers["knowledge_pack"] = l5_items

        filtered = ResolvedGenerationContext(
            layers=filtered_layers,
            source_catalog=filtered_catalog,
            conflict_pre_flags=resolved.conflict_pre_flags,
            suggested_chapter_enables=resolved.suggested_chapter_enables,
            user_chapter_selections=resolved.user_chapter_selections,
        )
        return filtered, missing_material_hints
