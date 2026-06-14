from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.models.prompt_config_version import PromptConfigVersion

GENERATION_PROMPT_NAME = "generation-chapter-draft"
GENERATION_PROMPT_VERSION = "generation-v1.0.0"

SYSTEM_PROMPT_TEMPLATE = """You are a technical bid-writing assistant for Chinese tender documents.

You receive layered tender constraints (rejection clauses, score points, outline structure, user selections, knowledge pack excerpts, and template hints) plus a Source Catalog of reference entries identified by ref_id.

Rules:
1. L1 rejection clauses are mandatory — never violate them.
2. L2 score points must be addressed in the draft.
3. L3 outline structure defines chapter placement; do not invent conflicting structure.
4. L6 template hints are reference only — they must not override L1–L3.
5. Every paragraph must cite at least one source_ref_id from the provided Source Catalog.
6. Use only ref_ids that appear in the Source Catalog; do not invent ref_ids.

Respond with valid JSON only (no markdown fences). Schema:
{
  "paragraphs": [
    {
      "text": "paragraph body with {{variables}} already substituted",
      "source_ref_ids": ["SRC-001", "TREQ-SP-0"],
      "addresses_score_points": ["SP-0"]
    }
  ],
  "generation_notes": "optional notes about missing materials or assumptions"
}
"""

USER_PROMPT_TEMPLATE = """Generate a chapter draft for the target outline node below.

Target outline node:
{target_outline_node}

Input priority layers:
{layers}

Source Catalog (use source_ref_ids from this list only):
{source_catalog}

Resolved variable values:
{variable_values}

Return JSON with paragraphs and source_ref_ids as specified in the system prompt.
"""


def seed_generation_prompt(db: Session, kb_id: UUID | None = None) -> PromptConfigVersion:
    del kb_id  # reserved for future kb-scoped prompt variants

    existing = (
        db.query(PromptConfigVersion)
        .filter(PromptConfigVersion.name == GENERATION_PROMPT_NAME)
        .filter(PromptConfigVersion.version_tag == GENERATION_PROMPT_VERSION)
        .one_or_none()
    )
    if existing is not None:
        return existing

    (
        db.query(PromptConfigVersion)
        .filter(PromptConfigVersion.name == GENERATION_PROMPT_NAME)
        .update({"is_active": False}, synchronize_session=False)
    )
    prompt = PromptConfigVersion(
        name=GENERATION_PROMPT_NAME,
        version_tag=GENERATION_PROMPT_VERSION,
        template_system=SYSTEM_PROMPT_TEMPLATE,
        template_user=USER_PROMPT_TEMPLATE,
        is_active=True,
    )
    db.add(prompt)
    db.flush()
    return prompt
