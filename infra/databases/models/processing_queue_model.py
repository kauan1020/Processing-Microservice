from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from . import Base

import uuid



class ProcessingQueueModel(Base):
    """
    SQLAlchemy model for processing queue entries persistence.

    This model represents the database schema for managing video processing
    job queue with priority handling, retry logic, and worker assignment
    tracking in PostgreSQL database.

    The model handles queue lifecycle management while maintaining
    separation from domain entities through repository pattern.
    """

    __tablename__ = "processing_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('video_jobs.id', ondelete='CASCADE'), nullable=False, unique=True,
                    index=True)
    user_id = Column(String(255), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=2, index=True)
    status = Column(String(50), nullable=False, default="queued", index=True)
    worker_id = Column(String(255), nullable=True, index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    scheduled_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    processing_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ProcessingQueue(id={self.id}, job_id={self.job_id}, status={self.status}, priority={self.priority})>"