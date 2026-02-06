"""
FoodCartOS Configuration

Loads configuration from environment variables with sensible defaults.
"""

from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars not defined here
    )

    # Application
    APP_ENV: str = "development"
    APP_NAME: str = "FoodCartOS"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"

    # URLs
    API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    # CORS
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Allowed CORS origins based on environment."""
        if self.APP_ENV == "development":
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        return [self.FRONTEND_URL]

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_ACCESS_TOKEN: Optional[str] = None
    DATABASE_URL: Optional[str] = None
    DATABASE_SCHEMA: str = "foodcartos"

    # Square
    SQUARE_ACCESS_TOKEN: str = ""
    SQUARE_APPLICATION_ID: str = ""
    SQUARE_LOCATION_ID: str = ""
    SQUARE_WEBHOOK_SIGNATURE_KEY: str = ""
    SQUARE_ENVIRONMENT: str = "sandbox"

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_MESSAGING_SERVICE_SID: str = ""

    # Weather
    OPENWEATHER_API_KEY: str = ""

    # n8n
    N8N_WEBHOOK_BASE_URL: str = ""

    # Hardware Agent
    AGENT_API_URL: str = ""
    AGENT_HARDWARE_ID: str = ""
    AGENT_ORG_ID: str = ""
    GPS_UPDATE_INTERVAL_SECONDS: int = 300
    GPS_GEOFENCE_RADIUS_METERS: int = 100
    PHOTO_QUALITY: int = 85
    PHOTO_MAX_WIDTH: int = 1920
    SYNC_INTERVAL_SECONDS: int = 60
    OFFLINE_QUEUE_MAX_SIZE: int = 1000

    # Development
    VERIFY_SSL: bool = True
    LOG_LEVEL: str = "INFO"


# Global settings instance
settings = Settings()
