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

    openai_api_key: str = ""  # embeddings (2.2); chat uses LLM_*

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-4.1-mini"

    chat_system_prompt: str = ""
    chat_history_max_messages: int = 20
    chat_history_max_chars: int = 24000
    chat_max_output_tokens: int = 4096

    frontend_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
