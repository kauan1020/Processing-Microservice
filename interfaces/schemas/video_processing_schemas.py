from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class JobStatusEnum(str, Enum):
    """Enumeration of possible job statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoFormatEnum(str, Enum):
    """Enumeration of supported video formats."""
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    MKV = "mkv"
    WEBM = "webm"
    WMV = "wmv"
    FLV = "flv"


class VideoInfoSchema(BaseModel):
    """Schema for video information."""
    original_filename: str = Field(..., description="Original name of the uploaded video file")
    file_size_mb: float = Field(..., description="File size in megabytes")
    video_format: VideoFormatEnum = Field(..., description="Video file format")
    duration: Optional[float] = Field(None, description="Video duration in seconds")
    extraction_fps: float = Field(..., description="Frames per second for extraction")


class JobSchema(BaseModel):
    """Schema for video processing job information."""
    id: str = Field(..., description="Unique identifier for the job")
    status: JobStatusEnum = Field(..., description="Current job status")
    queue_position: Optional[int] = Field(None, description="Position in processing queue")
    estimated_processing_time_minutes: Optional[float] = Field(None, description="Estimated processing time in minutes")
    estimated_frames: Optional[int] = Field(None, description="Estimated number of frames to extract")
    created_at: datetime = Field(..., description="Job creation timestamp")


class VideoSubmissionResponse(BaseModel):
    """Response schema for video submission."""
    success: bool = Field(True, description="Whether the submission was successful")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Job and video information")
    links: Dict[str, str] = Field(..., description="Related API endpoints")
    timestamp: datetime = Field(..., description="Response timestamp")


class ProgressSchema(BaseModel):
    """Schema for job progress information."""
    percentage: float = Field(..., description="Completion percentage (0-100)")
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time")
    processing_started_at: Optional[datetime] = Field(None, description="Processing start timestamp")
    processing_duration: Optional[float] = Field(None, description="Processing duration in seconds")


class ResultsSchema(BaseModel):
    """Schema for job results information."""
    frame_count: Optional[int] = Field(None, description="Number of frames extracted")
    estimated_frames: Optional[int] = Field(None, description="Estimated number of frames")
    zip_size_mb: Optional[float] = Field(None, description="ZIP file size in megabytes")
    download_available: bool = Field(..., description="Whether results are available for download")


class ErrorSchema(BaseModel):
    """Schema for error information."""
    message: str = Field(..., description="Error message")
    failed_at: Optional[datetime] = Field(None, description="Error timestamp")


class JobStatusResponse(BaseModel):
    """Response schema for job status."""
    success: bool = Field(True, description="Whether the request was successful")
    data: Dict[str, Any] = Field(..., description="Job status data")
    timestamp: datetime = Field(..., description="Response timestamp")


class PaginationSchema(BaseModel):
    """Schema for pagination information."""
    total_count: int = Field(..., description="Total number of items")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")
    has_next: bool = Field(..., description="Whether there are more items")
    has_previous: bool = Field(..., description="Whether there are previous items")
    total_pages: int = Field(..., description="Total number of pages")
    current_page: int = Field(..., description="Current page number")


class StatisticsSchema(BaseModel):
    """Schema for job statistics."""
    total_jobs: int = Field(..., description="Total number of jobs")
    completed_jobs: int = Field(..., description="Number of completed jobs")
    failed_jobs: int = Field(..., description="Number of failed jobs")
    pending_jobs: int = Field(..., description="Number of pending jobs")
    processing_jobs: int = Field(..., description="Number of processing jobs")
    total_frames_extracted: int = Field(..., description="Total frames extracted across all jobs")
    total_processing_time_hours: float = Field(..., description="Total processing time in hours")
    success_rate: float = Field(..., description="Success rate percentage")


class JobListResponse(BaseModel):
    """Response schema for job list."""
    success: bool = Field(True, description="Whether the request was successful")
    data: Dict[str, Any] = Field(..., description="Jobs list data with pagination and statistics")
    timestamp: datetime = Field(..., description="Response timestamp")


class DownloadInfoSchema(BaseModel):
    """Schema for download information."""
    filename: str = Field(..., description="Name of the download file")
    file_size_mb: float = Field(..., description="File size in megabytes")
    content_type: str = Field(..., description="MIME type of the file")
    job_info: Dict[str, Any] = Field(..., description="Related job information")


class JobDeletionResponse(BaseModel):
    """Response schema for job deletion."""
    success: bool = Field(True, description="Whether the deletion was successful")
    message: str = Field(..., description="Deletion confirmation message")
    data: Dict[str, Any] = Field(..., description="Deletion details")
    timestamp: datetime = Field(..., description="Response timestamp")


class ErrorResponse(BaseModel):
    """Response schema for errors."""
    success: bool = Field(False, description="Whether the request was successful")
    error: Dict[str, Any] = Field(..., description="Error information")
    timestamp: datetime = Field(..., description="Response timestamp")


class NotificationPreferencesSchema(BaseModel):
    """Schema for notification preferences."""
    email_enabled: bool = Field(True, description="Whether email notifications are enabled")
    job_completion: bool = Field(True, description="Notify on job completion")
    job_failure: bool = Field(True, description="Notify on job failure")
    progress_updates: bool = Field(False, description="Send progress update notifications")
    frequency: str = Field("immediate", description="Notification frequency")
    preferred_time: str = Field("any", description="Preferred notification time")


class SystemHealthSchema(BaseModel):
    """Schema for system health information."""
    status: str = Field(..., description="Overall system status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: str = Field(..., description="Health check timestamp")
    processing_capacity: Dict[str, Any] = Field(..., description="Processing capacity information")
    supported_formats: List[str] = Field(..., description="Supported video formats")
    max_file_size_mb: int = Field(..., description="Maximum file size in megabytes")
    max_processing_time_minutes: int = Field(..., description="Maximum processing time in minutes")


class SystemStatsSchema(BaseModel):
    """Schema for system statistics."""
    processing_stats: Dict[str, Any] = Field(..., description="Processing statistics")
    queue_stats: Dict[str, Any] = Field(..., description="Queue statistics")
    system_resources: Dict[str, Any] = Field(..., description="System resource usage")


class FrameListResponse(BaseModel):
    """Response schema for frame list."""
    frames: List[str] = Field(..., description="List of frame file names")

    class Config:
        schema_extra = {
            "example": {
                "frames": [
                    "frame_000001.png",
                    "frame_000002.png",
                    "frame_000003.png"
                ]
            }
        }


class CancellationResponse(BaseModel):
    """Response schema for job cancellation."""
    success: bool = Field(True, description="Whether the cancellation was successful")
    message: str = Field(..., description="Cancellation confirmation message")
    status: str = Field(..., description="New job status")


class BatchJobRequest(BaseModel):
    """Request schema for batch job operations."""
    job_ids: List[str] = Field(..., description="List of job IDs to process")
    operation: str = Field(..., description="Operation to perform on jobs")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Optional operation parameters")


class BatchJobResponse(BaseModel):
    """Response schema for batch job operations."""
    success: bool = Field(True, description="Whether the batch operation was successful")
    processed_count: int = Field(..., description="Number of jobs processed")
    failed_count: int = Field(..., description="Number of jobs that failed")
    results: List[Dict[str, Any]] = Field(..., description="Individual job results")
    timestamp: datetime = Field(..., description="Response timestamp")


class WebhookSchema(BaseModel):
    """Schema for webhook notifications."""
    event_type: str = Field(..., description="Type of event")
    job_id: str = Field(..., description="Job identifier")
    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(..., description="Event timestamp")
    data: Dict[str, Any] = Field(..., description="Event data")


class MetricsSchema(BaseModel):
    """Schema for processing metrics."""
    total_processing_time: float = Field(..., description="Total processing time in seconds")
    frames_per_second: float = Field(..., description="Processing rate in frames per second")
    cpu_usage_percent: float = Field(..., description="CPU usage percentage during processing")
    memory_usage_mb: float = Field(..., description="Memory usage in megabytes")
    disk_io_mb: float = Field(..., description="Disk I/O in megabytes")

    class Config:
        schema_extra = {
            "example": {
                "total_processing_time": 45.2,
                "frames_per_second": 2.5,
                "cpu_usage_percent": 78.5,
                "memory_usage_mb": 512.0,
                "disk_io_mb": 125.3
            }
        }