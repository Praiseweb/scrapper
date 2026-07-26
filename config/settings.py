import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    
    facebook_email: str = ""
    facebook_password: str = ""
    
    proxy_url: Optional[str] = None
    
    min_delay: int = 2
    max_delay: int = 5
    max_listings: int = 100
    
    output_dir: str = "output"
    log_dir: str = "logs"
    browser_state_dir: str = "browser_state"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__"
    )

settings = Settings()

os.makedirs(settings.output_dir, exist_ok=True)
os.makedirs(settings.log_dir, exist_ok=True)
os.makedirs(settings.browser_state_dir, exist_ok=True)
