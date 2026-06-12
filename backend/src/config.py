from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _discover_env_files() -> tuple[str, ...]:
    candidates = (_BACKEND_ROOT / ".env", _REPO_ROOT / ".env")
    found = tuple(str(path) for path in candidates if path.is_file())
    return found if found else (str(_REPO_ROOT / ".env"),)


# Preset profiles for quick provider switching via LLM_PROVIDER.
_LLM_PRESETS: dict[str, dict[str, str]] = {
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
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


settings = Settings()
