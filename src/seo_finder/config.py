from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SEO_", extra="ignore")

    user_agent: str = "SEOOpportunityFinder/0.1 (+https://example.com/bot)"
    max_pages: int = 20
    request_delay_seconds: float = 0.5
    request_timeout_seconds: float = 12.0
    google_places_api_key: Optional[str] = Field(
        default=None, validation_alias="GOOGLE_PLACES_API_KEY"
    )


settings = Settings()
