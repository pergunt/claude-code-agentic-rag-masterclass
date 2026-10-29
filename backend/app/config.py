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
    supabase_service_role_key: str = ""  # background ingestion only (app/services/ingestion.py)

    openai_api_key: str = ""  # embeddings (2.2); chat uses LLM_*
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536  # must match vector(1536) in the chunks table

    chunk_size: int = 1500  # characters
    chunk_overlap: int = 200
    max_upload_bytes: int = 5 * 1024 * 1024
    # Dev/test only: sleep before `processing` and before `completed` so a browser test can see each status.
    ingestion_stage_delay_seconds: float = 0

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-4.1-mini"

    chat_system_prompt: str = ""  # overrides DEFAULT_SYSTEM_PROMPT (services/prompts.py) when set
    chat_history_max_messages: int = 20
    chat_history_max_chars: int = 24000
    chat_max_output_tokens: int = 4096

    retrieval_top_k: int = 5
    # Cosine similarity; text-embedding-3-small scores run low (calibration: .env.example).
    retrieval_min_similarity: float = 0.15
    agent_max_tool_rounds: int = 3  # tool rounds per turn, then one final call with tool_choice="none"

    frontend_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
