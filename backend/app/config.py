from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# Load .env into os.environ too, so libraries that read env vars directly
# (LangSmith's LANGSMITH_* settings) see the same configuration.
load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    supabase_url: str = ""
    supabase_anon_key: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_vector_store_id: str = ""

    frontend_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
