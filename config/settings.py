import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _validate_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {var_name}")
    return value


@dataclass(frozen=True)
class AppSettings:
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", 800))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", 150))

    TOP_K: int = int(os.getenv("TOP_K", 4))

    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "huggingface")
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", 0.1))
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", 1024))

    GROQ_API_KEY: str = _validate_env("GROQ_API_KEY")

    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", 0.80))

    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", 15))

    UPLOAD_DIR: str = "data/uploads"
    FAISS_DIR: str = "data/faiss"
    OUTPUT_DIR: str = "output"


settings = AppSettings()
