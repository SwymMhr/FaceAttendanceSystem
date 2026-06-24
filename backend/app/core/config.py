# app/core/config.py
# This file reads your .env file and makes all settings available
# throughout the app via a single `settings` object.

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    MODEL_PATH: str = "model/face_embedding_model_mobilenetv2_v6_arcface.pth"
    UPLOAD_DIR: str = "uploads"

    class Config:
        # Tell pydantic-settings to read from your .env file
        env_file = ".env"

# Create one global instance — import this everywhere
settings = Settings()