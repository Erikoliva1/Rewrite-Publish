# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from passlib.hash import bcrypt
import logging
from pydantic import model_validator # Import model_validator

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    WORDPRESS_API_TOKEN: str
    WORDPRESS_APP_PASSWORD: str
    WORDPRESS_SITE_URL: str
    ACCESS_PASSWORD_HASH: str
    SESSION_TOKEN_FILE: str = "session_token.txt"

    @model_validator(mode='after')
    def validate_settings(self):
        # Validate critical WordPress settings
        if not self.WORDPRESS_SITE_URL:
            raise ValueError("WORDPRESS_SITE_URL environment variable must be set.")
        if not self.WORDPRESS_API_TOKEN:
            raise ValueError("WORDPRESS_API_TOKEN environment variable must be set.")
        if not self.WORDPRESS_APP_PASSWORD:
            raise ValueError("WORDPRESS_APP_PASSWORD environment variable must be set.")

        # Validate ACCESS_PASSWORD_HASH
        if not self.ACCESS_PASSWORD_HASH:
            raise ValueError("ACCESS_PASSWORD environment variable (bcrypt hash) must be set for authentication.")
        try:
            # Attempt a dummy verification to check if it's a valid bcrypt hash
            bcrypt.verify("test", self.ACCESS_PASSWORD_HASH)
            logger.info("ACCESS_PASSWORD_HASH loaded and appears to be a valid bcrypt hash.")
        except ValueError:
            raise ValueError("ACCESS_PASSWORD environment variable is not a valid bcrypt hash. Please generate one using `bcrypt.hash('your_password')`.")

        return self # Important: return self from a model_validator(mode='after')

# Initialize settings
try:
    settings = Settings()  # type: ignore [call-arg]
    pass # Suppress Pyright warning about missing arguments, as pydantic-settings handles env loading
    logger.info("Settings loaded successfully.")
except ValueError as e:
    logger.critical(f"Configuration Error: {e}")
    # Re-raise the error to ensure the application doesn't start with invalid config
    raise

