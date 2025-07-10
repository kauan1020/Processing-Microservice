from pydantic_settings import BaseSettings
from typing import List, Optional
from pydantic import Field



class DatabaseSettings(BaseSettings):
    """Database configuration settings for PostgreSQL connectivity and connection pool management."""
    host: str = "localhost"
    port: int = 5432
    name: str = "video_processing"
    user: str = "postgres"
    password: str = ""
    url: Optional[str] = None
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600

    class Config:
        env_prefix = "DATABASE_"


class ProcessingSettings(BaseSettings):
    """Video processing configuration settings for FFmpeg operations and job management."""
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    max_file_size_mb: int = 500
    max_concurrent_jobs: int = 4
    max_concurrent_jobs_per_worker: int = 2
    job_timeout_minutes: int = 60
    temp_cleanup_hours: int = 24
    retry_attempts: int = 3
    retry_delay_seconds: int = 60

    class Config:
        env_prefix = "PROCESSING_"


class StorageSettings(BaseSettings):
    """File storage configuration settings for video files and extracted frames."""
    base_path: str = "/app/storage"
    video_path: str = "/app/storage/videos"
    frames_path: str = "/app/storage/frames"
    zip_path: str = "/app/storage/results"
    temp_path: str = "/app/storage/temp"
    max_disk_usage_percent: int = 85
    cleanup_old_files_days: int = 30

    class Config:
        env_prefix = "STORAGE_"


class KafkaSettings(BaseSettings):
    """Kafka messaging configuration settings for job queue and event streaming."""
    bootstrap_servers: str = "localhost:9092"
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: str = "PLAIN"
    sasl_username: str = ""
    sasl_password: str = ""
    topic_video_jobs: str = "video_jobs"
    topic_notifications: str = "notifications"
    topic_processing: str = "video_processing"
    topic_system_alerts: str = "system_alerts"
    group_id: str = "video_processing_group"
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = False
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 10000

    class Config:
        env_prefix = "KAFKA_"


class AuthSettings(BaseSettings):
    """Authentication service configuration settings for JWT token validation."""
    service_url: str = "http://localhost:8000"
    api_key: str = ""
    validate_token_endpoint: str = "/auth/validate"
    user_info_endpoint: str = "/users/profile"
    retry_attempts: int = 3
    cache_ttl_seconds: int = 300
    timeout: int = 30

    class Config:
        env_prefix = "AUTH_"


class UserServiceSettings(BaseSettings):
    """User service configuration settings for user management and preferences."""
    service_url: str = "http://localhost:8000"
    timeout: int = 30
    api_key: str = ""
    retry_attempts: int = 3
    cache_ttl_seconds: int = 300

    class Config:
        env_prefix = "USER_SERVICE_"


class NotificationSettings(BaseSettings):
    """Notification service configuration settings for email notifications via Gmail."""
    service_url: str = "http://localhost:8003"
    api_key: str = ""
    gmail_email: str = ""
    gmail_app_password: str = ""
    from_email: str = ""
    from_name: str = "FIAP X Video Processing"
    admin_emails: str = ""
    retry_attempts: int = 3
    timeout: int = 30

    def get_admin_emails_list(self) -> List[str]:
        """Parse admin emails string into list of email addresses."""
        return [email.strip() for email in self.admin_emails.split(',') if email.strip()]

    class Config:
        env_prefix = "NOTIFICATION_"


class CorsSettings(BaseSettings):
    """CORS configuration settings for cross-origin resource sharing policies."""
    allowed_origins: str = "*"
    allow_credentials: bool = True
    allowed_methods: str = "*"
    allowed_headers: str = "*"

    def get_allowed_origins_list(self) -> List[str]:
        """Parse allowed origins string into list of origin URLs."""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(',') if origin.strip()]

    def get_allowed_methods_list(self) -> List[str]:
        """Parse allowed methods string into list of HTTP methods."""
        if self.allowed_methods == "*":
            return ["*"]
        return [method.strip() for method in self.allowed_methods.split(',') if method.strip()]

    class Config:
        env_prefix = "CORS_"


class Settings(BaseSettings):
    """
    Main application settings aggregating all configuration sections.

    This class serves as the central configuration hub for the video processing
    microservice, providing access to all subsystem configurations including
    database connectivity, processing parameters, storage locations, messaging
    systems, authentication services, and cross-cutting concerns.
    """
    app_name: str = "FIAP X Video Processing Service"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8001
    workers: int = 1
    database_url: Optional[str] = None

    database: DatabaseSettings = DatabaseSettings()
    processing: ProcessingSettings = ProcessingSettings()
    storage: StorageSettings = StorageSettings()
    kafka: KafkaSettings = KafkaSettings()
    auth: AuthSettings = Field(default_factory=AuthSettings)
    user_service: UserServiceSettings = Field(default_factory=UserServiceSettings)
    notification: NotificationSettings = NotificationSettings()
    cors: CorsSettings = CorsSettings()

    def __init__(self, **kwargs):
        """Initialize settings with automatic database URL configuration if not provided."""
        super().__init__(**kwargs)
        if not self.database_url and not self.database.url:
            self.database.url = f"postgresql+asyncpg://{self.database.user}:{self.database.password}@{self.database.host}:{self.database.port}/{self.database.name}"

    class Config:
        env_prefix = "APP_"
        case_sensitive = False
        extra = "ignore"


def get_settings() -> Settings:
    """Get configured application settings instance with all environment variables loaded."""
    return Settings()