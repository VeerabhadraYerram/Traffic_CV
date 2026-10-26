"""
config.py — Centralized configuration management for UC4 (ANPR & Vehicle Access Logging).
Uses Pydantic BaseSettings for type-safe environment configuration with fallback.
"""

import os
from typing import Optional

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field

    class Settings(BaseSettings):
        # Service Identification
        SERVICE_NAME: str = Field(default="uc4-anpr")
        SERVICE_PORT: int = Field(default=8004)
        ENVIRONMENT: str = Field(default="production")
        LOG_LEVEL: str = Field(default="INFO")

        # Redis Streams
        REDIS_HOST: str = Field(default="innovision-redis")
        REDIS_PORT: int = Field(default=6379)
        REDIS_PASSWORD: Optional[str] = Field(default=None)
        REDIS_DB: int = Field(default=0)

        FRAME_STREAM_NAME: str = Field(default="streams:frames")
        FRAME_CONSUMER_GROUP: str = Field(default="group:uc4:anpr")
        FRAME_CONSUMER_ID: str = Field(default="anpr-worker-1")
        ALERT_STREAM_NAME: str = Field(default="streams:alerts")

        # Backpressure Controls
        MAX_FRAME_AGE_MS: int = Field(default=150)
        STREAM_BATCH_SIZE: int = Field(default=8)

        # Inference Configuration
        INFERENCE_MODE: str = Field(default="local_worker")  # "hybrid" | "shared_server" | "local_worker"
        SHARED_INFERENCE_URL: str = Field(default="http://innovision-inference:8500/v1/predict")
        LOCAL_GPU_DEVICE: int = Field(default=0)
        LOCAL_BATCH_SIZE: int = Field(default=8)
        MAX_CONCURRENT_OCR: int = Field(default=3)

        # Platform Integration
        PLATFORM_API_BASE: str = Field(default="http://innovision-platform:8000/api/v1")
        PLATFORM_SERVICE_TOKEN: str = Field(default="internal-service-secret")
        CAMERA_SYNC_INTERVAL_SEC: int = Field(default=30)

        # Database Configuration
        DATABASE_URL: str = Field(default="postgresql://admin:adminpassword@innovision-db:5432/uc4_anpr")
        DATA_RETENTION_DAYS: int = Field(default=30)

        # Snapshot Storage
        SNAPSHOT_DIR: str = Field(default="/app/snapshots")

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"

    settings = Settings()

except ImportError:
    # Lightweight fallback if pydantic_settings is not yet installed in host environment
    class FallbackSettings:
        SERVICE_NAME: str = os.getenv("SERVICE_NAME", "uc4-anpr")
        SERVICE_PORT: int = int(os.getenv("SERVICE_PORT", "8004"))
        ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
        LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

        REDIS_HOST: str = os.getenv("REDIS_HOST", "innovision-redis")
        REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
        REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD") or None
        REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

        FRAME_STREAM_NAME: str = os.getenv("FRAME_STREAM_NAME", "streams:frames")
        FRAME_CONSUMER_GROUP: str = os.getenv("FRAME_CONSUMER_GROUP", "group:uc4:anpr")
        FRAME_CONSUMER_ID: str = os.getenv("FRAME_CONSUMER_ID", "anpr-worker-1")
        ALERT_STREAM_NAME: str = os.getenv("ALERT_STREAM_NAME", "streams:alerts")

        MAX_FRAME_AGE_MS: int = int(os.getenv("MAX_FRAME_AGE_MS", "150"))
        STREAM_BATCH_SIZE: int = int(os.getenv("STREAM_BATCH_SIZE", "8"))

        INFERENCE_MODE: str = os.getenv("INFERENCE_MODE", "local_worker")
        SHARED_INFERENCE_URL: str = os.getenv("SHARED_INFERENCE_URL", "http://innovision-inference:8500/v1/predict")
        LOCAL_GPU_DEVICE: int = int(os.getenv("LOCAL_GPU_DEVICE", "0"))
        LOCAL_BATCH_SIZE: int = int(os.getenv("LOCAL_BATCH_SIZE", "8"))
        MAX_CONCURRENT_OCR: int = int(os.getenv("MAX_CONCURRENT_OCR", "3"))

        PLATFORM_API_BASE: str = os.getenv("PLATFORM_API_BASE", "http://innovision-platform:8000/api/v1")
        PLATFORM_SERVICE_TOKEN: str = os.getenv("PLATFORM_SERVICE_TOKEN", "internal-service-secret")
        CAMERA_SYNC_INTERVAL_SEC: int = int(os.getenv("CAMERA_SYNC_INTERVAL_SEC", "30"))

        DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://admin:adminpassword@innovision-db:5432/uc4_anpr")
        DATA_RETENTION_DAYS: int = int(os.getenv("DATA_RETENTION_DAYS", "30"))

        SNAPSHOT_DIR: str = os.getenv("SNAPSHOT_DIR", "/app/snapshots")

    settings = FallbackSettings()
