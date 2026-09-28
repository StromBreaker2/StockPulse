import os
from pathlib import Path
from dotenv import load_dotenv

# Search for .env in current directory and parent directories
env_paths = [
    Path.cwd() / ".env",
    Path.cwd() / "backend" / ".env",
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
]
for p in env_paths:
    if p.exists():
        load_dotenv(p)
        break

class Settings:
    # Database
    database_url: str = os.getenv("DATABASE_URL", "")
    
    # LLM Settings
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://litellm-qc.zycus.net/v1")
    llm_model: str = os.getenv("LLM_MODEL", "qwen-cursor")
    llm_product: str = os.getenv("LLM_PRODUCT", "PC1")
    llm_cookie: str = os.getenv("LLM_COOKIE", "")
    
    # Business Logic
    demand_spike_multiplier: float = float(os.getenv("DEMAND_SPIKE_MULTIPLIER", "3.0"))
    
    # Strategy
    default_strategy: str = os.getenv("DEFAULT_STRATEGY", "AI")

settings = Settings()