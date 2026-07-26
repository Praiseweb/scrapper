import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """Application settings."""
    
    # Facebook Credentials
    facebook_email: str = ""
    facebook_password: str = ""
    
    # Proxy Configuration
    proxy_url: Optional[str] = None
    
    # Scraper Settings
    min_delay: int = 2
    max_delay: int = 5
    max_listings: int = 100
    
    # Data Storage
    output_dir: str = "output"
    log_dir: str = "logs"
    browser_state_dir: str = "browser_state"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__"
    )

# Instantiate settings
settings = Settings()

# Ensure directories exist
os.makedirs(settings.output_dir, exist_ok=True)
os.makedirs(settings.log_dir, exist_ok=True)
os.makedirs(settings.browser_state_dir, exist_ok=True)
