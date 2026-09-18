import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Settings:
    """Configuración global para Vig-IA."""
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_DEFAULT_MODEL: str = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5-coder:7b")

    EXTERNO_PROVIDER: str = os.getenv("EXTERNO_PROVIDER", "gemini")
    EXTERNO_API_KEY: str = os.getenv("EXTERNO_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or EXTERNO_API_KEY
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    EXTERNO_DEFAULT_MODEL: str = os.getenv("EXTERNO_DEFAULT_MODEL", "gemini-3.6-flash")
    EXTERNO_BASE_URL: str = os.getenv("EXTERNO_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")

    COSTO_INPUT_1K_TOKENS: float = 0.00059
    COSTO_OUTPUT_1K_TOKENS: float = 0.00079


settings = Settings()