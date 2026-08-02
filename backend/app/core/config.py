# app/core/config.py
# This file reads your .env file and makes all settings available
# throughout the app via a single `settings` object.

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    MODEL_PATH: str = "model/face_embedding_model_mobilenetv2_v6_arcface.pth"
    UPLOAD_DIR: str = "uploads"

    # ── Auth settings ──────────────────────────────────────────────────────
    # SECRET_KEY should be overridden in your .env file in any real deployment
    # (generate one with: python -c "import secrets; print(secrets.token_hex(32))")
    SECRET_KEY: str = "dev-only-change-me-in-.env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # ── Email settings (absence notifications) ─────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_FROM_EMAIL: str

    # ── Liveness detection ────────────────────────────────────────────────
    LIVENESS_ENABLED: bool = True
    LIVENESS_MIN_CHECKS_TO_FAIL: int = 2

    # ── CCTV integration ─────────────────────────────────────────────────
    CCTV_ENABLED: bool = False
    CCTV_RTSP_URL: str = ""
    CCTV_STREAM_FALLBACKS: str = ""
    CCTV_BATCH_ID: int | None = None
    CCTV_STREAM_FPS: float = 15.0
    CCTV_CAPTURE_MIN_INTERVAL: float = 1.0
    CCTV_CAPTURE_MAX_INTERVAL: float = 5.0

    class Config:
        # Tell pydantic-settings to read from your .env file
        env_file = ".env"

# Create one global instance — import this everywhere
settings = Settings()