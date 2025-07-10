"""Configuration management using Pydantic Settings"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation"""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="AI_NEWS_", case_sensitive=False
    )

    # Schedule (cron format)
    daily_schedule: str = Field(
        default="0 17 * * 1-5",  # Mon-Fri 20:00 MSK (17:00 UTC)
        description="Cron schedule for daily digest",
    )
    weekly_schedule: str = Field(
        default="0 8 * * 6",  # Sat 11:00 MSK (08:00 UTC)
        description="Cron schedule for weekly summary",
    )
    timezone: str = Field(default="Europe/Moscow")

    # Storage
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/news.db",
        description="Database connection URL",
    )
    data_dir: Path = Field(default=Path("./data"))
    output_dir: Path = Field(default=Path("./output"))

    # RSS Sources
    rss_feeds: list[dict] = Field(
        default=[
            {
                "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
                "name": "TechCrunch AI",
            },
            {
                "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
                "name": "The Verge AI",
            },
            {"url": "https://arxiv.org/rss/cs.AI", "name": "ArXiv AI Papers"},
            {"url": "https://openai.com/blog/rss.xml", "name": "OpenAI Blog"},
            {"url": "https://www.anthropic.com/rss.xml", "name": "Anthropic Blog"},
        ]
    )

    # Processing
    max_age_days: int = Field(default=7, ge=1, le=30)
    title_similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    content_similarity_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    min_content_length: int = Field(default=100, ge=10)

    # Network
    request_timeout: int = Field(default=30, ge=5, le=300)
    max_retries: int = Field(default=3, ge=1, le=10)
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(
        default="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Optional: AI APIs (for future)
    anthropic_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)

    def create_directories(self) -> None:
        """Ensure all required directories exist"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "daily").mkdir(exist_ok=True)
        (self.output_dir / "weekly").mkdir(exist_ok=True)


# Global settings instance
settings = Settings()
