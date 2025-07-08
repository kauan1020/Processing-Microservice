from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from domain.value_objects import VideoFile, FrameExtractionConfig, ProcessingResult
from domain.entities.video_job import VideoJob


class VideoProcessorInterface(ABC):
    """
    Service interface for video processing operations.

    This interface defines the contract for video processing operations
    including frame extraction, video analysis, and file manipulation.

    The implementation should handle FFmpeg integration and provide
    robust video processing capabilities with error handling.
    """

    @abstractmethod
    async def extract_frames(self,
                             video_file: VideoFile,
                             config: FrameExtractionConfig,
                             output_directory: str) -> ProcessingResult:
        """
        Extract frames from a video file according to the specified configuration.

        Args:
            video_file: Video file to process
            config: Frame extraction configuration
            output_directory: Directory to save extracted frames

        Returns:
            ProcessingResult: Result of the frame extraction operation

        Raises:
            FFmpegException: If FFmpeg processing fails
            StorageException: If file operations fail
        """
        pass

    @abstractmethod
    async def get_video_info(self, video_file: VideoFile) -> Dict[str, Any]:
        """
        Get detailed information about a video file.

        Args:
            video_file: Video file to analyze

        Returns:
            Dict[str, Any]: Dictionary containing video metadata:
                - duration: Video duration in seconds
                - frame_rate: Frames per second
                - resolution: Video resolution as (width, height)
                - codec: Video codec information
                - bitrate: Video bitrate
                - format: Container format

        Raises:
            VideoCorruptedException: If video file is corrupted
            FFmpegException: If analysis fails
        """
        pass

    @abstractmethod
    async def validate_video_file(self, video_file: VideoFile) -> bool:
        """
        Validate that a video file is readable and processable.

        Args:
            video_file: Video file to validate

        Returns:
            bool: True if video is valid and processable, False otherwise
        """
        pass

    @abstractmethod
    async def estimate_processing_time(self,
                                       video_file: VideoFile,
                                       config: FrameExtractionConfig) -> float:
        """
        Estimate the time required to process a video file.

        Args:
            video_file: Video file to process
            config: Frame extraction configuration

        Returns:
            float: Estimated processing time in seconds
        """
        pass

    @abstractmethod
    async def cancel_processing(self, job_id: str) -> bool:
        """
        Cancel an ongoing video processing operation.

        Args:
            job_id: ID of the job to cancel

        Returns:
            bool: True if cancellation was successful, False otherwise
        """
        pass


class FileStorageInterface(ABC):
    """
    Service interface for file storage operations.

    This interface defines the contract for file storage operations
    including video upload, frame storage, and ZIP file creation.

    The implementation should handle local file system or cloud storage
    operations with proper error handling and security measures.
    """

    @abstractmethod
    async def store_video_file(self,
                               file_content: bytes,
                               filename: str,
                               user_id: str) -> str:
        """
        Store an uploaded video file.

        Args:
            file_content: Binary content of the video file
            filename: Original filename
            user_id: ID of the user uploading the file

        Returns:
            str: Path to the stored video file

        Raises:
            StorageException: If storage operation fails
        """
        pass

    @abstractmethod
    async def create_zip_archive(self,
                                 frame_files: List[str],
                                 output_path: str) -> int:
        """
        Create a ZIP archive containing the extracted frames.

        Args:
            frame_files: List of paths to frame files
            output_path: Path where ZIP file should be created

        Returns:
            int: Size of the created ZIP file in bytes

        Raises:
            StorageException: If ZIP creation fails
        """
        pass

    @abstractmethod
    async def get_file_size(self, file_path: str) -> int:
        """
        Get the size of a file in bytes.

        Args:
            file_path: Path to the file

        Returns:
            int: File size in bytes

        Raises:
            StorageException: If file cannot be accessed
        """
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from storage.

        Args:
            file_path: Path to the file to delete

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        pass

    @abstractmethod
    async def delete_directory(self, directory_path: str) -> bool:
        """
        Delete a directory and all its contents.

        Args:
            directory_path: Path to the directory to delete

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        pass

    @abstractmethod
    async def ensure_directory_exists(self, directory_path: str) -> None:
        """
        Ensure that a directory exists, creating it if necessary.

        Args:
            directory_path: Path to the directory

        Raises:
            StorageException: If directory cannot be created
        """
        pass

    @abstractmethod
    async def get_available_space(self) -> int:
        """
        Get available storage space in bytes.

        Returns:
            int: Available space in bytes
        """
        pass


class QueueServiceInterface(ABC):
    """
    Service interface for queue management operations.

    This interface defines the contract for queue operations including
    job queuing, worker management, and queue monitoring.

    The implementation should handle message queuing systems like
    RabbitMQ, Redis, or in-memory queues with proper reliability.
    """

    @abstractmethod
    async def enqueue_job(self, job: VideoJob, priority: int = 1) -> bool:
        """
        Add a video job to the processing queue.

        Args:
            job: Video job to queue for processing
            priority: Priority level (higher numbers = higher priority)

        Returns:
            bool: True if job was successfully queued, False otherwise

        Raises:
            QueueException: If queueing operation fails
        """
        pass

    @abstractmethod
    async def dequeue_job(self, worker_id: str) -> Optional[VideoJob]:
        """
        Get the next job from the queue for processing.

        Args:
            worker_id: ID of the worker requesting a job

        Returns:
            Optional[VideoJob]: Next job to process or None if queue is empty
        """
        pass

    @abstractmethod
    async def acknowledge_job(self, job_id: str, worker_id: str) -> bool:
        """
        Acknowledge that a job has been successfully processed.

        Args:
            job_id: ID of the completed job
            worker_id: ID of the worker that processed the job

        Returns:
            bool: True if acknowledgment was successful, False otherwise
        """
        pass

    @abstractmethod
    async def reject_job(self, job_id: str, worker_id: str, reason: str) -> bool:
        """
        Reject a job and return it to the queue for retry.

        Args:
            job_id: ID of the failed job
            worker_id: ID of the worker that rejected the job
            reason: Reason for rejection

        Returns:
            bool: True if rejection was successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status and statistics.

        Returns:
            Dict[str, Any]: Dictionary containing queue statistics:
                - pending_jobs: Number of jobs waiting to be processed
                - processing_jobs: Number of jobs currently being processed
                - failed_jobs: Number of failed jobs
                - active_workers: Number of active workers
                - queue_health: Overall queue health status
        """
        pass

    @abstractmethod
    async def cleanup_stale_jobs(self, timeout_minutes: int = 60) -> int:
        """
        Clean up jobs that have been processing for too long.

        Args:
            timeout_minutes: Maximum processing time before considering a job stale

        Returns:
            int: Number of stale jobs cleaned up
        """
        pass


class NotificationServiceInterface(ABC):
    """
    Service interface for notification operations.

    This interface defines the contract for sending notifications
    about job status changes, completion, and errors.

    The implementation should handle integration with AWS Lambda,
    email services, or other notification systems.
    """

    @abstractmethod
    async def notify_job_completed(self, job: VideoJob, user_email: str) -> bool:
        """
        Send notification when a job completes successfully.

        Args:
            job: Completed video job
            user_email: Email address to notify

        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def notify_job_failed(self, job: VideoJob, user_email: str, error_message: str) -> bool:
        """
        Send notification when a job fails.

        Args:
            job: Failed video job
            user_email: Email address to notify
            error_message: Description of the failure

        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def notify_system_alert(self, alert_type: str, message: str) -> bool:
        """
        Send system-level alerts for monitoring and maintenance.

        Args:
            alert_type: Type of alert (error, warning, info)
            message: Alert message

        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        pass