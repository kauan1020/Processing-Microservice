from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class QueuePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class QueueStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class ProcessingQueue:
    """
    Processing queue entity representing a queued video processing task.

    This entity manages the queueing system for video processing jobs,
    including priority handling, retry logic, and worker assignment.

    Attributes:
        id: Unique identifier for the queue entry
        job_id: ID of the associated video job
        user_id: ID of the user who owns the job
        priority: Processing priority level
        status: Current queue status
        worker_id: ID of the worker processing this job
        retry_count: Number of processing retry attempts
        max_retries: Maximum number of retry attempts allowed
        scheduled_at: Timestamp when job should be processed
        started_at: Timestamp when processing started
        completed_at: Timestamp when processing completed
        error_message: Last error message if processing failed
        processing_data: Additional processing configuration data
        created_at: Timestamp when queue entry was created
        updated_at: Timestamp when queue entry was last updated
    """

    id: Optional[str]
    job_id: str
    user_id: str
    priority: QueuePriority
    status: QueueStatus
    worker_id: Optional[str]
    retry_count: int
    max_retries: int
    scheduled_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    processing_data: Optional[Dict[str, Any]]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    def is_queued(self) -> bool:
        """
        Check if the queue entry is waiting to be processed.

        Returns:
            bool: True if status is queued, False otherwise
        """
        return self.status == QueueStatus.QUEUED

    def is_processing(self) -> bool:
        """
        Check if the queue entry is currently being processed.

        Returns:
            bool: True if status is processing, False otherwise
        """
        return self.status == QueueStatus.PROCESSING

    def is_completed(self) -> bool:
        """
        Check if the queue entry has completed processing.

        Returns:
            bool: True if status is completed, False otherwise
        """
        return self.status == QueueStatus.COMPLETED

    def is_failed(self) -> bool:
        """
        Check if the queue entry has failed processing.

        Returns:
            bool: True if status is failed, False otherwise
        """
        return self.status == QueueStatus.FAILED

    def can_retry(self) -> bool:
        """
        Check if the queue entry can be retried.

        Returns:
            bool: True if retry count is below maximum, False otherwise
        """
        return self.retry_count < self.max_retries

    def should_be_processed(self) -> bool:
        """
        Check if the queue entry should be processed now.

        Returns:
            bool: True if scheduled time has passed and status allows processing
        """
        now = datetime.utcnow()
        return (self.scheduled_at <= now and
                self.status in [QueueStatus.QUEUED, QueueStatus.RETRY])

    def assign_worker(self, worker_id: str) -> None:
        """
        Assign a worker to process this queue entry.

        Args:
            worker_id: Identifier of the worker taking this job
        """
        self.worker_id = worker_id
        self.status = QueueStatus.PROCESSING
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def complete_processing(self) -> None:
        """
        Mark the queue entry as completed successfully.
        """
        self.status = QueueStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def fail_processing(self, error_message: str) -> None:
        """
        Mark the queue entry as failed and increment retry count.

        Args:
            error_message: Description of the processing error
        """
        self.error_message = error_message
        self.retry_count += 1
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        if self.can_retry():
            self.status = QueueStatus.RETRY
            self.worker_id = None
            self.scheduled_at = self._calculate_retry_delay()
        else:
            self.status = QueueStatus.FAILED

    def reset_for_retry(self) -> None:
        """
        Reset the queue entry for retry processing.
        """
        self.status = QueueStatus.QUEUED
        self.worker_id = None
        self.started_at = None
        self.completed_at = None
        self.scheduled_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def get_wait_time(self) -> float:
        """
        Calculate how long the job has been waiting in queue.

        Returns:
            float: Wait time in seconds
        """
        if not self.created_at:
            return 0.0

        reference_time = self.started_at or datetime.utcnow()
        return (reference_time - self.created_at).total_seconds()

    def get_processing_time(self) -> Optional[float]:
        """
        Calculate how long the job has been/was processing.

        Returns:
            Optional[float]: Processing time in seconds or None if not started
        """
        if not self.started_at:
            return None

        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()

    def get_priority_weight(self) -> int:
        """
        Get numerical weight for priority comparison.

        Returns:
            int: Priority weight (higher number = higher priority)
        """
        return self.priority.value

    def is_high_priority(self) -> bool:
        """
        Check if this queue entry has high or urgent priority.

        Returns:
            bool: True if priority is high or urgent, False otherwise
        """
        return self.priority in [QueuePriority.HIGH, QueuePriority.URGENT]

    def _calculate_retry_delay(self) -> datetime:
        """
        Calculate the next retry time using exponential backoff.

        Returns:
            datetime: Timestamp when retry should be attempted
        """
        base_delay = 60
        exponential_delay = base_delay * (2 ** (self.retry_count - 1))
        max_delay = 1800

        delay_seconds = min(exponential_delay, max_delay)

        from datetime import timedelta
        return datetime.utcnow() + timedelta(seconds=delay_seconds)

    def update_processing_data(self, key: str, value: Any) -> None:
        """
        Update processing data with new key-value pair.

        Args:
            key: Data key
            value: Data value
        """
        if self.processing_data is None:
            self.processing_data = {}

        self.processing_data[key] = value
        self.updated_at = datetime.utcnow()