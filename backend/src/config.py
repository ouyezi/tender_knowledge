from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    storage_root: str = "data/uploads"
    llm_api_key: str | None = None
    max_file_size_docx_mb: int = 50
    max_file_size_pdf_mb: int = 50
    max_file_size_ppt_mb: int = 50
    max_file_size_xlsx_mb: int = 20
    max_file_size_image_mb: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
