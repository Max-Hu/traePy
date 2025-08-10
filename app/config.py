import os
import logging
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "TraePy API"
    DEBUG: bool = os.getenv("DEBUG", True)
    PORT: int = int(os.getenv("PORT", 8000))
    

    
    # JWT authentication settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    
    # Database settings
    ORACLE_USER: str = os.getenv("ORACLE_USER", "system")
    ORACLE_PASSWORD: str = os.getenv("ORACLE_PASSWORD", "oracle")
    ORACLE_HOST: str = os.getenv("ORACLE_HOST", "localhost")
    ORACLE_PORT: int = int(os.getenv("ORACLE_PORT", 1521))
    ORACLE_SERVICE: str = os.getenv("ORACLE_SERVICE", "XEPDB1")
    
    # Jenkins settings
    JENKINS_URL: str = os.getenv("JENKINS_URL", "http://jenkins:8080")
    JENKINS_USER: str = os.getenv("JENKINS_USER", "maxhu")
    JENKINS_TOKEN: str = os.getenv("JENKINS_TOKEN", "11d5f70116f1e97c95b2471aef26c2a1c9")
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = os.getenv("LOG_FILE", "")
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True
    )

settings = Settings()