from pathlib import Path
from typing import List, Union, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json

# Base directory for backend
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "TruthTrace Backend"
    API_V1_STR: str = "/api"
    HOST: str = "127.0.0.1"
    PORT: int = 8001
    DEBUG: bool = True
    
    # CORS Configuration
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Preprocessing & Chunking (Tokens)
    CHUNK_TARGET_TOKENS: int = 500
    CHUNK_MIN_TOKENS: int = 150
    CHUNK_MAX_TOKENS: int = 800
    CHUNK_OVERLAP_TOKENS: int = 60

    # Embeddings & Vector Store (FAISS)
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    VECTOR_STORE_DIR: Path = BASE_DIR.parent / "data" / "vector_store"
    FAISS_INDEX_FILE: str = "index.faiss"
    FAISS_METADATA_FILE: str = "metadata.json"

    # LLM — Google Gemini (optional: heuristic fallback used if not set)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"

    # News source API keys (optional — RSS works without any keys)
    NEWS_API_KEY: Optional[str] = None
    GOOGLE_FACT_CHECK_API_KEY: Optional[str] = None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
