from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime
from domain.entities.processing_queue import ProcessingQueue, QueueStatus, QueuePriority


class ProcessingQueueRepositoryInterface(ABC):
    """
    Repository interface for ProcessingQueue entity operations.

    This interface defines the contract for processing queue data persistence operations,
    following the Repository pattern to abstract data access concerns from
    the business logic layer.

    The implementation should handle all database operations related to queue
    management, including CRUD operations, worker assignment, and queue monitoring.
    """

    @abstractmethod
    async def create(self, queue_entry: ProcessingQueue) -> ProcessingQueue:
        """
        Create a new queue entry in the repository.

        Args:
            queue_entry: ProcessingQueue entity to be created

        Returns:
            ProcessingQueue: Created queue entry with generated ID and timestamps
        """
        pass

    @abstractmethod
    async def find_by_id(self, queue_id: str) -> Optional[ProcessingQueue]:
        """
        Find a queue entry by its unique identifier.

        Args:
            queue_id: Unique identifier of the queue entry

        Returns:
            Optional[ProcessingQueue]: ProcessingQueue entity if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_by_job_id(self, job_id: str) -> Optional[ProcessingQueue]:
        """
        Find a queue entry by associated job ID.

        Args:
            job_id: Video job identifier

        Returns:
            Optional[ProcessingQueue]: ProcessingQueue entity if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_next_available_jobs(self, limit: int = 10) -> List[ProcessingQueue]:
        """
        Find next available jobs ready for processing, ordered by priority and creation time.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List[ProcessingQueue]: List of queue entries ready for processing
        """
        pass

    @abstractmethod
    async def assign_worker(self, queue_id: str, worker_id: str) -> bool:
        """
        Assign a worker to a queue entry and mark it as processing.

        Args:
            queue_id: Queue entry identifier
            worker_id: Worker identifier

        Returns:
            bool: True if assignment was successful, False otherwise
        """
        pass

    @abstractmethod
    async def update(self, queue_entry: ProcessingQueue) -> ProcessingQueue:
        """
        Update an existing queue entry in the repository.

        Args:
            queue_entry: ProcessingQueue entity with updated information

        Returns:
            ProcessingQueue: Updated queue entry entity
        """
        pass

    @abstractmethod
    async def delete(self, queue_id: str) -> bool:
        """
        Delete a queue entry from the repository.

        Args:
            queue_id: Unique identifier of the queue entry to delete

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        pass

    @abstractmethod
    async def find_by_status(self, status: QueueStatus, skip: int = 0, limit: int = 100) -> List[ProcessingQueue]:
        """
        Find queue entries by their status.

        Args:
            status: Queue status to filter by
            skip: Number of entries to skip
            limit: Maximum number of entries to return

        Returns:
            List[ProcessingQueue]: List of queue entries with the specified status
        """
        pass

    @abstractmethod
    async def find_stale_processing_entries(self, timeout_minutes: int = 60) -> List[ProcessingQueue]:
        """
        Find queue entries that have been processing for longer than the timeout period.

        Args:
            timeout_minutes: Maximum processing time before considering an entry stale

        Returns:
            List[ProcessingQueue]: List of entries that may be stuck in processing
        """
        pass

    @abstractmethod
    async def count_by_status(self, status: QueueStatus) -> int:
        """
        Count the total number of queue entries with a specific status.

        Args:
            status: Queue status to count

        Returns:
            int: Total number of entries with the specified status
        """
        pass

    @abstractmethod
    async def get_queue_statistics(self) -> dict:
        """
        Get comprehensive queue statistics.

        Returns:
            dict: Dictionary containing queue statistics with keys:
                - total_entries: Total number of queue entries
                - queued_entries: Number of entries waiting to be processed
                - processing_entries: Number of entries currently being processed
                - completed_entries: Number of completed entries
                - failed_entries: Number of failed entries
                - retry_entries: Number of entries waiting for retry
                - average_wait_time: Average time jobs spend waiting in queue
                - average_processing_time: Average processing time for completed jobs
        """
        pass

    @abstractmethod
    async def cleanup_completed_entries(self, days_old: int = 7) -> int:
        """
        Clean up completed queue entries older than specified number of days.

        Args:
            days_old: Number of days to keep completed entries before cleanup

        Returns:
            int: Number of entries cleaned up
        """
        pass