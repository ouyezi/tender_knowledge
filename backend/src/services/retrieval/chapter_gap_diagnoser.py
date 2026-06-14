from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


DEFAULT_GAP_THRESHOLD = {"min_frequency": 3, "min_ratio": 0.3}


@dataclass(slots=True)
class ChapterGapDiagnoser:
    threshold: dict[str, float] | None = None

    def __post_init__(self) -> None:
        merged = dict(DEFAULT_GAP_THRESHOLD)
        if self.threshold:
            merged.update(self.threshold)
        self.threshold = merged

    def diagnose(
        self,
        *,
        matched_pattern_ids: list[UUID],
        candidate_patterns: list[dict],
    ) -> list[dict[str, object]]:
        if not candidate_patterns:
            return []

        assert self.threshold is not None
        top_frequency = max(int(item.get("frequency", 0)) for item in candidate_patterns)
        min_frequency = int(self.threshold["min_frequency"])
        min_ratio = float(self.threshold["min_ratio"])
        matched_set = {str(item) for item in matched_pattern_ids}
        missing: list[dict[str, object]] = []
        for item in candidate_patterns:
            pattern_id = str(item["pattern_id"])
            frequency = int(item.get("frequency", 0))
            if pattern_id in matched_set:
                continue
            if frequency < min_frequency:
                continue
            if top_frequency <= 0 or (frequency / top_frequency) < min_ratio:
                continue
            missing.append(
                {
                    "pattern_id": pattern_id,
                    "pattern_name": item.get("pattern_name") or "",
                    "frequency": frequency,
                    "reason": "产品分类下高频章节未覆盖",
                }
            )
        return missing
