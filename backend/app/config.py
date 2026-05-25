from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ollama_base_url: str = "http://ollama:11434"
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    embed_model: str = "all-minilm"
    chat_model: str = "llama3.2:3b"

    # utf-8-sig strips the BOM that Windows PowerShell adds to UTF-8 files
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
    )


settings = Settings()
