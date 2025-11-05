"""
Production-Ready Configuration Management
Validates all environment variables on startup and provides type-safe configuration
"""

import os
import secrets
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum


class Environment(Enum):
    """Application environment"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ConfigurationError(Exception):
    """Raised when configuration is invalid"""
    pass


@dataclass(frozen=True)
class Config:
    """Application configuration with validation"""

    # Environment
    ENVIRONMENT: Environment
    DEBUG: bool

    # Security
    SECRET_KEY: str
    JWT_SECRET_KEY: str
    JWT_ACCESS_TOKEN_EXPIRES: int  # seconds
    JWT_REFRESH_TOKEN_EXPIRES: int  # seconds

    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_PROJECT_ID: str
    REDIRECT_URI: str
    FRONTEND_URL: str

    # Database
    DATABASE_PATH: str
    DATABASE_POOL_SIZE: int
    DATABASE_MAX_OVERFLOW: int
    DATABASE_POOL_TIMEOUT: int

    # Redis (for caching and rate limiting)
    REDIS_URL: Optional[str]
    REDIS_ENABLED: bool

    # Rate Limiting
    RATELIMIT_ENABLED: bool
    RATELIMIT_STORAGE_URL: Optional[str]
    RATELIMIT_STRATEGY: str

    # Application Limits
    MAX_EMAILS_PER_REQUEST: int
    MAX_ACTIVITIES_PER_USER: int
    SESSION_LIFETIME_MINUTES: int
    OAUTH_STATE_TTL_MINUTES: int

    # Gmail API
    GMAIL_API_TIMEOUT: int
    GMAIL_API_MAX_RETRIES: int
    GMAIL_API_BACKOFF_FACTOR: float

    # Logging
    LOG_LEVEL: str
    LOG_FORMAT: str
    STRUCTURED_LOGGING: bool

    # CORS
    CORS_ORIGINS: List[str]
    CORS_CREDENTIALS: bool

    # Security Headers
    CSP_ENABLED: bool
    HSTS_ENABLED: bool
    HSTS_MAX_AGE: int

    # Monitoring
    SENTRY_DSN: Optional[str]
    PROMETHEUS_ENABLED: bool

    # Background Jobs
    CELERY_BROKER_URL: Optional[str]
    CELERY_RESULT_BACKEND: Optional[str]
    CELERY_ENABLED: bool

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.ENVIRONMENT == Environment.DEVELOPMENT

    def validate(self) -> None:
        """Validate configuration"""
        errors = []

        # Validate SECRET_KEY
        if len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be at least 32 characters")

        # Validate JWT_SECRET_KEY
        if len(self.JWT_SECRET_KEY) < 32:
            errors.append("JWT_SECRET_KEY must be at least 32 characters")

        # Validate Google OAuth
        if not self.GOOGLE_CLIENT_ID:
            errors.append("GOOGLE_CLIENT_ID is required")
        if not self.GOOGLE_CLIENT_SECRET:
            errors.append("GOOGLE_CLIENT_SECRET is required")
        if not self.GOOGLE_PROJECT_ID:
            errors.append("GOOGLE_PROJECT_ID is required")

        # Validate URLs
        if not self.REDIRECT_URI.startswith('http'):
            errors.append("REDIRECT_URI must be a valid URL")
        if not self.FRONTEND_URL.startswith('http'):
            errors.append("FRONTEND_URL must be a valid URL")

        # Production-specific validations
        if self.is_production:
            if self.DEBUG:
                errors.append("DEBUG must be False in production")
            if not self.REDIRECT_URI.startswith('https'):
                errors.append("REDIRECT_URI must use HTTPS in production")
            if not self.FRONTEND_URL.startswith('https'):
                errors.append("FRONTEND_URL must use HTTPS in production")
            if not self.REDIS_ENABLED:
                errors.append("Redis is required in production for rate limiting and caching")
            if not self.HSTS_ENABLED:
                errors.append("HSTS must be enabled in production")

        if errors:
            raise ConfigurationError("\n".join(errors))


def get_config() -> Config:
    """Load and validate configuration from environment variables"""

    # Get environment
    env_str = os.getenv('ENVIRONMENT', 'development').lower()
    try:
        environment = Environment(env_str)
    except ValueError:
        raise ConfigurationError(f"Invalid ENVIRONMENT: {env_str}. Must be one of: development, staging, production")

    # Security keys (REQUIRED - fail fast if not set)
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        if environment == Environment.DEVELOPMENT:
            # Allow auto-generation in development only, with warning
            secret_key = secrets.token_hex(32)
            print("WARNING: SECRET_KEY not set. Generated temporary key for development.")
            print("This key will change on restart. Set SECRET_KEY in production!")
        else:
            raise ConfigurationError("SECRET_KEY environment variable is required in staging/production")

    jwt_secret_key = os.getenv('JWT_SECRET_KEY', secret_key)

    # Google OAuth (REQUIRED)
    google_client_id = os.getenv('GOOGLE_CLIENT_ID', '')
    google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '')
    google_project_id = os.getenv('GOOGLE_PROJECT_ID', '')

    # URLs
    redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:5000/oauth2callback')
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:8000')

    # Database
    database_path = os.getenv('DATABASE_PATH', 'gmail_unsubscriber.db')
    database_pool_size = int(os.getenv('DATABASE_POOL_SIZE', '10'))
    database_max_overflow = int(os.getenv('DATABASE_MAX_OVERFLOW', '20'))
    database_pool_timeout = int(os.getenv('DATABASE_POOL_TIMEOUT', '30'))

    # Redis
    redis_url = os.getenv('REDIS_URL')
    redis_enabled = os.getenv('REDIS_ENABLED', 'true' if environment == Environment.PRODUCTION else 'false').lower() == 'true'

    # Rate Limiting
    ratelimit_enabled = os.getenv('RATELIMIT_ENABLED', 'true' if environment == Environment.PRODUCTION else 'false').lower() == 'true'
    ratelimit_storage_url = os.getenv('RATELIMIT_STORAGE_URL', redis_url)
    ratelimit_strategy = os.getenv('RATELIMIT_STRATEGY', 'fixed-window')

    # Application limits
    max_emails_per_request = int(os.getenv('MAX_EMAILS_PER_REQUEST', '200'))
    max_activities_per_user = int(os.getenv('MAX_ACTIVITIES_PER_USER', '50'))
    session_lifetime_minutes = int(os.getenv('SESSION_LIFETIME_MINUTES', '15'))
    oauth_state_ttl_minutes = int(os.getenv('OAUTH_STATE_TTL_MINUTES', '10'))

    # Gmail API
    gmail_api_timeout = int(os.getenv('GMAIL_API_TIMEOUT', '30'))
    gmail_api_max_retries = int(os.getenv('GMAIL_API_MAX_RETRIES', '3'))
    gmail_api_backoff_factor = float(os.getenv('GMAIL_API_BACKOFF_FACTOR', '2.0'))

    # Logging
    log_level = os.getenv('LOG_LEVEL', 'INFO' if environment == Environment.PRODUCTION else 'DEBUG')
    log_format = os.getenv('LOG_FORMAT', 'json' if environment == Environment.PRODUCTION else 'text')
    structured_logging = os.getenv('STRUCTURED_LOGGING', 'true' if environment == Environment.PRODUCTION else 'false').lower() == 'true'

    # CORS
    cors_origins_str = os.getenv('CORS_ORIGINS', frontend_url)
    cors_origins = [origin.strip() for origin in cors_origins_str.split(',')]
    cors_credentials = os.getenv('CORS_CREDENTIALS', 'true').lower() == 'true'

    # Security Headers
    csp_enabled = os.getenv('CSP_ENABLED', 'true' if environment == Environment.PRODUCTION else 'false').lower() == 'true'
    hsts_enabled = os.getenv('HSTS_ENABLED', 'true' if environment == Environment.PRODUCTION else 'false').lower() == 'true'
    hsts_max_age = int(os.getenv('HSTS_MAX_AGE', '31536000'))  # 1 year

    # Monitoring
    sentry_dsn = os.getenv('SENTRY_DSN')
    prometheus_enabled = os.getenv('PROMETHEUS_ENABLED', 'true' if environment == Environment.PRODUCTION else 'false').lower() == 'true'

    # Background Jobs
    celery_broker_url = os.getenv('CELERY_BROKER_URL', redis_url)
    celery_result_backend = os.getenv('CELERY_RESULT_BACKEND', redis_url)
    celery_enabled = os.getenv('CELERY_ENABLED', 'false').lower() == 'true'

    config = Config(
        ENVIRONMENT=environment,
        DEBUG=environment == Environment.DEVELOPMENT,
        SECRET_KEY=secret_key,
        JWT_SECRET_KEY=jwt_secret_key,
        JWT_ACCESS_TOKEN_EXPIRES=900,  # 15 minutes
        JWT_REFRESH_TOKEN_EXPIRES=604800,  # 7 days
        GOOGLE_CLIENT_ID=google_client_id,
        GOOGLE_CLIENT_SECRET=google_client_secret,
        GOOGLE_PROJECT_ID=google_project_id,
        REDIRECT_URI=redirect_uri,
        FRONTEND_URL=frontend_url,
        DATABASE_PATH=database_path,
        DATABASE_POOL_SIZE=database_pool_size,
        DATABASE_MAX_OVERFLOW=database_max_overflow,
        DATABASE_POOL_TIMEOUT=database_pool_timeout,
        REDIS_URL=redis_url,
        REDIS_ENABLED=redis_enabled,
        RATELIMIT_ENABLED=ratelimit_enabled,
        RATELIMIT_STORAGE_URL=ratelimit_storage_url,
        RATELIMIT_STRATEGY=ratelimit_strategy,
        MAX_EMAILS_PER_REQUEST=max_emails_per_request,
        MAX_ACTIVITIES_PER_USER=max_activities_per_user,
        SESSION_LIFETIME_MINUTES=session_lifetime_minutes,
        OAUTH_STATE_TTL_MINUTES=oauth_state_ttl_minutes,
        GMAIL_API_TIMEOUT=gmail_api_timeout,
        GMAIL_API_MAX_RETRIES=gmail_api_max_retries,
        GMAIL_API_BACKOFF_FACTOR=gmail_api_backoff_factor,
        LOG_LEVEL=log_level,
        LOG_FORMAT=log_format,
        STRUCTURED_LOGGING=structured_logging,
        CORS_ORIGINS=cors_origins,
        CORS_CREDENTIALS=cors_credentials,
        CSP_ENABLED=csp_enabled,
        HSTS_ENABLED=hsts_enabled,
        HSTS_MAX_AGE=hsts_max_age,
        SENTRY_DSN=sentry_dsn,
        PROMETHEUS_ENABLED=prometheus_enabled,
        CELERY_BROKER_URL=celery_broker_url,
        CELERY_RESULT_BACKEND=celery_result_backend,
        CELERY_ENABLED=celery_enabled,
    )

    # Validate configuration
    config.validate()

    return config


# Global config instance
_config: Optional[Config] = None


def init_config() -> Config:
    """Initialize global configuration"""
    global _config
    if _config is None:
        _config = get_config()
    return _config


def get_current_config() -> Config:
    """Get current configuration (must be initialized first)"""
    if _config is None:
        raise ConfigurationError("Configuration not initialized. Call init_config() first.")
    return _config
