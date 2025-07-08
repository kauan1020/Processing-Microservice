from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoFormat(Enum):
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    MKV = "mkv"
    WEBM = "webm"
    WMV = "wmv"
    FLV = "flv"


@dataclass
class VideoJob:
    """
    Video processing job entity representing a video frame extraction task.

    This entity encapsulates all information related to a video processing job,
    including metadata, status tracking, and processing configuration.

    Attributes:
        id: Unique identifier for the video job
        user_id: ID of the user who submitted the job
        original_filename: Original name of the uploaded video file
        file_path: Path to the stored video file
        file_size: Size of the video file in bytes
        video_format: Format of the video file
        duration: Duration of the video in seconds
        frame_rate: Original frame rate of the video
        extraction_fps: Frames per second for extraction (default 1)
        status: Current processing status
        frame_count: Number of frames extracted
        zip_file_path: Path to the generated ZIP file
        zip_file_size: Size of the ZIP file in bytes
        error_message: Error message if processing failed
        processing_started_at: Timestamp when processing started
        processing_completed_at: Timestamp when processing completed
        created_at: Timestamp when job was created
        updated_at: Timestamp when job was last updated
        metadata: Additional metadata as JSON
    """

    id: Optional[str]
    user_id: str
    original_filename: str
    file_path: str
    file_size: int
    video_format: VideoFormat
    duration: Optional[float]
    frame_rate: Optional[float]
    extraction_fps: float
    status: JobStatus
    frame_count: Optional[int]
    zip_file_path: Optional[str]
    zip_file_size: Optional[int]
    error_message: Optional[str]
    processing_started_at: Optional[datetime]
    processing_completed_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    metadata: Optional[Dict[str, Any]]

    def is_pending(self) -> bool:
        """
        Check if the job is in pending status.

        Returns:
            bool: True if job status is pending, False otherwise
        """
        return self.status == JobStatus.PENDING

    def is_processing(self) -> bool:
        """
        Check if the job is currently being processed.

        Returns:
            bool: True if job status is processing, False otherwise
        """
        return self.status == JobStatus.PROCESSING

    def is_completed(self) -> bool:
        """
        Check if the job has completed successfully.

        Returns:
            bool: True if job status is completed, False otherwise
        """
        return self.status == JobStatus.COMPLETED

    def is_failed(self) -> bool:
        """
        Check if the job has failed.

        Returns:
            bool: True if job status is failed, False otherwise
        """
        return self.status == JobStatus.FAILED

    def is_cancelled(self) -> bool:
        """
        Check if the job has been cancelled.

        Returns:
            bool: True if job status is cancelled, False otherwise
        """
        return self.status == JobStatus.CANCELLED

    def can_be_processed(self) -> bool:
        """
        Check if the job can be processed (is in pending status).

        Returns:
            bool: True if job can be processed, False otherwise
        """
        return self.status == JobStatus.PENDING

    def start_processing(self) -> None:
        """
        Mark the job as started processing and update timestamps.
        """
        self.status = JobStatus.PROCESSING
        self.processing_started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def complete_processing(self, frame_count: int, zip_path: str, zip_size: int) -> None:
        """
        Mark the job as completed with processing results.

        Args:
            frame_count: Number of frames extracted
            zip_path: Path to the generated ZIP file
            zip_size: Size of the ZIP file in bytes
        """
        self.status = JobStatus.COMPLETED
        self.frame_count = frame_count
        self.zip_file_path = zip_path
        self.zip_file_size = zip_size
        self.processing_completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def fail_processing(self, error_message: str) -> None:
        """
        Mark the job as failed with error information.

        Args:
            error_message: Description of the processing error
        """
        self.status = JobStatus.FAILED
        self.error_message = error_message
        self.processing_completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def cancel_processing(self) -> None:
        """
        Cancel the job processing.
        """
        self.status = JobStatus.CANCELLED
        self.updated_at = datetime.utcnow()

    def get_processing_duration(self) -> Optional[float]:
        """
        Calculate the processing duration in seconds.

        Returns:
            Optional[float]: Processing duration in seconds or None if not applicable
        """
        if not self.processing_started_at:
            return None

        end_time = self.processing_completed_at or datetime.utcnow()
        duration = end_time - self.processing_started_at
        return duration.total_seconds()

    def update_metadata(self, key: str, value: Any) -> None:
        """
        Update a specific metadata field.

        Args:
            key: Metadata key
            value: Metadata value
        """
        if self.metadata is None:
            self.metadata = {}

        self.metadata[key] = value
        self.updated_at = datetime.utcnow()

    def get_estimated_frames(self) -> Optional[int]:
        """
        Estimate the number of frames that will be extracted.

        Returns:
            Optional[int]: Estimated frame count or None if duration unknown
        """
        if not self.duration:
            return None

        return int(self.duration * self.extraction_fps)

    def get_file_size_mb(self) -> float:
        """
        Get file size in megabytes.

        Returns:
            float: File size in MB
        """
        return self.file_size / (1024 * 1024)

    def get_zip_size_mb(self) -> Optional[float]:
        """
        Get ZIP file size in megabytes.

        Returns:
            Optional[float]: ZIP file size in MB or None if not available
        """
        if not self.zip_file_size:
            return None

        return self.zip_file_size / (1024 * 1024)