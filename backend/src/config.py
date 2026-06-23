from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _discover_env_files() -> tuple[str, ...]:
    candidates = (_BACKEND_ROOT / ".env", _REPO_ROOT / ".env")
    found = tuple(str(path) for path in candidates if path.is_file())
    return found if found else (str(_REPO_ROOT / ".env"),)


# Preset profiles for quick provider switching via LLM_PROVIDER.
# Embedding (百炼 OpenAI 兼容): https://help.aliyun.com/zh/model-studio/developer-reference/text-embedding-synchronous-api
_LLM_PRESETS: dict[str, dict[str, str]] = {
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "embedding_model": "text-embedding-v4",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
}


class Settings(BaseSettings):
    storage_root: str = "data/uploads"

    # LLM — switch provider by changing LLM_PROVIDER in .env (qwen | openai | custom).
    llm_provider: str = "qwen"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_max_chunk_chars: int = 8000
    llm_request_timeout_sec: int = 60

    max_file_size_docx_mb: int = 50
    max_file_size_pdf_mb: int = 50
    max_file_size_ppt_mb: int = 50
    max_file_size_xlsx_mb: int = 20
    max_file_size_image_mb: int = 10

    use_doc_chunk_parse: bool = True
    doc_chunk_skip_enrich: bool = False
    doc_chunk_workspace_retention_on_success: bool = False
    doc_chunk_workspace_retention_hours: int = 24
    doc_chunk_classification_config: str | None = None

    knowledge_prefill_model: str = "qwen3-max"
    knowledge_prefill_timeout_sec: int = 10
    blueprint_generate_model: str = "qwen3.6-flash"
    blueprint_generate_timeout_sec: int = 120
    blueprint_generate_max_tokens: int = 16384
    blueprint_suggest_model: str = "qwen3.6-flash"
    blueprint_suggest_timeout_sec: int = 120
    blueprint_suggest_max_tokens: int = 8192
    blueprint_suggest_max_blueprints: int = 5
    blueprint_suggest_requirement_max: int = 2000
    blueprint_search_parse_model: str = "qwen3.6-flash"
    blueprint_search_parse_timeout_sec: int = 30
    blueprint_search_parse_query_max: int = 500
    blueprint_search_name_keyword_weight: float = 3.0
    blueprint_search_body_keyword_weight: float = 1.0
    blueprint_search_vector_min_similarity: float = 0.10
    blueprint_search_exact_match_boost: float = 0.35
    embedding_model: str = "text-embedding-v4"
    embedding_dimensions: int = 1024
    # Optional overrides; when unset, embedding uses the same Qwen/OpenAI-compatible endpoint as LLM.
    embedding_api_base: str | None = None
    embedding_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=_discover_env_files(), extra="ignore")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def resolved_llm_base_url(self) -> str:
        if self.llm_base_url:
            return self.llm_base_url
        preset = _LLM_PRESETS.get(self.llm_provider.lower(), _LLM_PRESETS["qwen"])
        return preset["base_url"]

    @property
    def resolved_llm_model(self) -> str:
        if self.llm_model:
            return self.llm_model
        preset = _LLM_PRESETS.get(self.llm_provider.lower(), _LLM_PRESETS["qwen"])
        return preset["model"]

    @property
    def resolved_embedding_api_base(self) -> str:
        if self.embedding_api_base:
            return self.embedding_api_base.strip()
        return self.resolved_llm_base_url

    @property
    def resolved_embedding_api_key(self) -> str:
        if self.embedding_api_key:
            return self.embedding_api_key.strip()
        return (self.llm_api_key or "").strip()

    @property
    def embedding_enabled(self) -> bool:
        return bool(self.resolved_embedding_api_base and self.resolved_embedding_api_key)


settings = Settings()
