from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class VideoJobModel(Base):
    """
    SQLAlchemy model for video processing jobs.

    This model represents the database table structure for storing
    video processing job information with all necessary fields for
    tracking job lifecycle, metadata, and processing results.
    """

    __tablename__ = "video_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, nullable=False)
    video_format = Column(String(10), nullable=False)
    duration = Column(Float, nullable=True)
    frame_rate = Column(Float, nullable=True)
    extraction_fps = Column(Float, nullable=False, default=1.0)
    status = Column(String(20), nullable=False, default="pending", index=True)
    frame_count = Column(Integer, nullable=True)
    zip_file_path = Column(String(1000), nullable=True)
    zip_file_size = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    job_metadata = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<VideoJob(id={self.id}, filename={self.original_filename}, status={self.status})>"


class ProcessingQueueModel(Base):
    """
    SQLAlchemy model for processing queue entries.

    This model represents the database table structure for managing
    the video processing queue with priority handling, retry logic,
    and worker assignment tracking.
    """

    __tablename__ = "processing_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=2, index=True)
    status = Column(String(20), nullable=False, default="queued", index=True)
    worker_id = Column(String(255), nullable=True, index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    scheduled_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    processing_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ProcessingQueue(id={self.id}, job_id={self.job_id}, status={self.status})>"


class WorkerModel(Base):
    """
    SQLAlchemy model for worker instances.

    This model represents the database table structure for tracking
    worker instances in the distributed video processing system
    with health monitoring and capacity management.
    """

    __tablename__ = "workers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    worker_id = Column(String(255), nullable=False, unique=True, index=True)
    hostname = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=True)
    port = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="idle", index=True)
    max_concurrent_jobs = Column(Integer, nullable=False, default=1)
    current_job_count = Column(Integer, nullable=False, default=0)
    total_jobs_processed = Column(Integer, nullable=False, default=0)
    total_processing_time = Column(Float, nullable=False, default=0.0)
    last_heartbeat = Column(DateTime, nullable=False, default=func.now(), index=True)
    capabilities = Column(JSON, nullable=True)
    resource_usage = Column(JSON, nullable=True)
    version = Column(String(50), nullable=True)
    started_at = Column(DateTime, nullable=False, default=func.now())
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Worker(id={self.id}, worker_id={self.worker_id}, status={self.status})>"


class NotificationLogModel(Base):
    """
    SQLAlchemy model for notification tracking.

    This model represents the database table structure for logging
    notification delivery attempts and tracking delivery status
    for audit and monitoring purposes.
    """

    __tablename__ = "notification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    notification_type = Column(String(50), nullable=False, index=True)
    recipient_email = Column(String(320), nullable=False, index=True)
    subject = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    delivery_attempts = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    notification_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<NotificationLog(id={self.id}, type={self.notification_type}, status={self.status})>"


class SystemMetricsModel(Base):
    """
    SQLAlchemy model for system metrics and monitoring.

    This model represents the database table structure for storing
    system performance metrics, resource usage, and operational
    statistics for monitoring and analytics purposes.
    """

    __tablename__ = "system_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    metric_type = Column(String(50), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=True)
    tags = Column(JSON, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)
    worker_id = Column(String(255), nullable=True, index=True)
    job_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

    def __repr__(self):
        return f"<SystemMetrics(id={self.id}, name={self.metric_name}, value={self.metric_value})>"


class AuditLogModel(Base):
    """
    SQLAlchemy model for audit logging.

    This model represents the database table structure for audit
    trail logging to track user actions, system events, and
    administrative operations for security and compliance.
    """

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String(255), nullable=True, index=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    success = Column(Boolean, nullable=False, default=True, index=True)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, resource={self.resource_type})>"


class FileStorageModel(Base):
    """
    SQLAlchemy model for file storage tracking.

    This model represents the database table structure for tracking
    stored files, their locations, sizes, and metadata for storage
    management and cleanup operations.
    """

    __tablename__ = "file_storage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    file_type = Column(String(20), nullable=False, index=True)
    file_path = Column(String(1000), nullable=False, unique=True)
    original_filename = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=True)
    checksum = Column(String(64), nullable=True)
    storage_backend = Column(String(50), nullable=False, default="local")
    is_temporary = Column(Boolean, nullable=False, default=False, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    accessed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<FileStorage(id={self.id}, path={self.file_path}, type={self.file_type})>"