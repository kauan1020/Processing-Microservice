from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime
from domain.entities.video_job import VideoJob, JobStatus


class VideoJobRepositoryInterface(ABC):
    """
    Repository interface for VideoJob entity operations.

    This interface defines the contract for video job data persistence operations,
    following the Repository pattern to abstract data access concerns from
    the business logic layer.

    The implementation should handle all database operations related to video
    job management, including CRUD operations and specialized queries for
    job status tracking and user-specific operations.
    """

    @abstractmethod
    async def create(self, job: VideoJob) -> VideoJob:
        """
        Create a new video job in the repository.

        Args:
            job: VideoJob entity to be created

        Returns:
            VideoJob: Created job with generated ID and timestamps
        """
        pass

    @abstractmethod
    async def find_by_id(self, job_id: str) -> Optional[VideoJob]:
        """
        Find a video job by its unique identifier.

        Args:
            job_id: Unique identifier of the video job

        Returns:
            Optional[VideoJob]: VideoJob entity if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_by_user_id(self, user_id: str, skip: int = 0, limit: int = 100) -> List[VideoJob]:
        """
        Find video jobs belonging to a specific user with pagination.

        Args:
            user_id: User identifier
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return

        Returns:
            List[VideoJob]: List of video jobs for the user
        """
        pass

    @abstractmethod
    async def find_by_status(self, status: JobStatus, skip: int = 0, limit: int = 100) -> List[VideoJob]:
        """
        Find video jobs by their processing status.

        Args:
            status: Job status to filter by
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return

        Returns:
            List[VideoJob]: List of jobs with the specified status
        """
        pass

    @abstractmethod
    async def find_user_job_by_id(self, job_id: str, user_id: str) -> Optional[VideoJob]:
        """
        Find a video job by ID that belongs to a specific user.

        Args:
            job_id: Unique identifier of the video job
            user_id: User identifier for authorization

        Returns:
            Optional[VideoJob]: VideoJob entity if found and owned by user, None otherwise
        """
        pass

    @abstractmethod
    async def update(self, job: VideoJob) -> VideoJob:
        """
        Update an existing video job in the repository.

        Args:
            job: VideoJob entity with updated information

        Returns:
            VideoJob: Updated job entity

        Raises:
            VideoJobNotFoundException: If job doesn't exist
        """
        pass

    @abstractmethod
    async def delete(self, job_id: str) -> bool:
        """
        Delete a video job from the repository.

        Args:
            job_id: Unique identifier of the job to delete

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        pass

    @abstractmethod
    async def count_by_user_id(self, user_id: str) -> int:
        """
        Count the total number of jobs for a specific user.

        Args:
            user_id: User identifier

        Returns:
            int: Total number of jobs for the user
        """
        pass

    @abstractmethod
    async def count_by_status(self, status: JobStatus) -> int:
        """
        Count the total number of jobs with a specific status.

        Args:
            status: Job status to count

        Returns:
            int: Total number of jobs with the specified status
        """
        pass

    @abstractmethod
    async def find_pending_jobs(self, limit: int = 50) -> List[VideoJob]:
        """
        Find jobs that are pending processing, ordered by creation time.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List[VideoJob]: List of pending jobs ordered by oldest first
        """
        pass

    @abstractmethod
    async def find_stale_processing_jobs(self, timeout_minutes: int = 60) -> List[VideoJob]:
        """
        Find jobs that have been processing for longer than the timeout period.

        Args:
            timeout_minutes: Maximum processing time before considering a job stale

        Returns:
            List[VideoJob]: List of jobs that may be stuck in processing
        """
        pass

    @abstractmethod
    async def find_jobs_by_date_range(self,
                                      start_date: datetime,
                                      end_date: datetime,
                                      user_id: Optional[str] = None) -> List[VideoJob]:
        """
        Find jobs created within a specific date range.

        Args:
            start_date: Start of the date range
            end_date: End of the date range
            user_id: Optional user ID to filter by specific user

        Returns:
            List[VideoJob]: List of jobs created within the date range
        """
        pass

    @abstractmethod
    async def get_user_job_statistics(self, user_id: str) -> dict:
        """
        Get job statistics for a specific user.

        Args:
            user_id: User identifier

        Returns:
            dict: Dictionary containing job statistics with keys:
                - total_jobs: Total number of jobs
                - completed_jobs: Number of completed jobs
                - failed_jobs: Number of failed jobs
                - pending_jobs: Number of pending jobs
                - processing_jobs: Number of currently processing jobs
                - total_frames_extracted: Total frames across all jobs
                - total_processing_time: Total processing time in seconds
        """
        pass

    @abstractmethod
    async def cleanup_old_jobs(self, days_old: int = 30) -> int:
        """
        Clean up jobs older than specified number of days.

        This method should handle cleanup of associated files and database records
        for jobs that are older than the specified threshold.

        Args:
            days_old: Number of days to keep jobs before cleanup

        Returns:
            int: Number of jobs cleaned up
        """
        pass