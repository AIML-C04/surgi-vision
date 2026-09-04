import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Explicitly load .env from the project root
root_dir = Path(__file__).resolve().parents[3]
env_path = root_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "SurgiVision AI"
    
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "surgivision")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "surgivision")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite:///./surgivision.db"
    )
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "mock")
    MODEL_ENDPOINT: str = os.getenv("MODEL_ENDPOINT", "")
    PHASE_MODEL_PROVIDER: str = os.getenv("PHASE_MODEL_PROVIDER", "none")
    LIVE_INFERENCE_ENABLED: bool = os.getenv("LIVE_INFERENCE_ENABLED", "true").lower() == "true"
    LIVE_MAX_QUEUE_SIZE: int = int(os.getenv("LIVE_MAX_QUEUE_SIZE", "1"))
    
    class Config:
        case_sensitive = True

settings = Settings()
