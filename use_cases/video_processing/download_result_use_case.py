from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import os

from domain.entities.video_job import VideoJob
from domain.exceptions import (
    VideoJobNotFoundException,
    AuthorizationException,
    InvalidJobStatusException,
    StorageException
)
from interfaces.repositories.video_job_repository_interface import VideoJobRepositoryInterface
from interfaces.services.file_storage_interface import FileStorageInterface


@dataclass
class DownloadResultRequest:
    """
    Request data structure for downloading processing results.

    Contains job identification and user authorization information
    for accessing completed video processing results.

    Attributes:
        job_id: ID of the video job to download results for
        user_id: ID of the user requesting the download
        include_metadata: Whether to include processing metadata
    """
    job_id: str
    user_id: str
    include_metadata: bool = False


@dataclass
class DownloadResultResponse:
    """
    Response data structure for download processing results.

    Contains file information and content for downloading the
    processed video frames as a ZIP archive.

    Attributes:
        success: Whether the download request was successful
        file_path: Path to the ZIP file containing extracted frames
        file_size: Size of the ZIP file in bytes
        filename: Suggested filename for download
        content_type: MIME type for the file
        job_data: Job information for download tracking
        metadata: Optional processing metadata
    """
    success: bool
    file_path: str
    file_size: int
    filename: str
    content_type: str
    job_data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class DeleteJobRequest:
    """
    Request data structure for deleting a video job.

    Contains job identification and user authorization for
    removing jobs and associated files from the system.

    Attributes:
        job_id: ID of the video job to delete
        user_id: ID of the user requesting deletion
        delete_files: Whether to delete associated files
    """
    job_id: str
    user_id: str
    delete_files: bool = True


@dataclass
class DeleteJobResponse:
    """
    Response data structure for job deletion operations.

    Contains the result of job deletion including cleanup status
    and any files that were removed.

    Attributes:
        success: Whether the deletion was successful
        job_id: ID of the deleted job
        message: Status message about the deletion
        files_deleted: List of files that were removed
    """
    success: bool
    job_id: str
    message: str
    files_deleted: list


class DownloadProcessingResultUseCase:
    """
    Use case for downloading completed video processing results.

    This use case handles requests for downloading ZIP files containing
    extracted frames from completed video processing jobs, with proper
    authorization and file availability validation.
    """

    def __init__(self,
                 job_repository: VideoJobRepositoryInterface,
                 file_storage: FileStorageInterface):
        """
        Initialize the download processing result use case.

        Args:
            job_repository: Repository for video job data operations
            file_storage: Service for file storage operations
        """
        self.job_repository = job_repository
        self.file_storage = file_storage

    async def execute(self, request: DownloadResultRequest) -> DownloadResultResponse:
        """
        Execute the download processing result use case.

        Args:
            request: Download request containing job and user information

        Returns:
            DownloadResultResponse: Download information and file details

        Raises:
            VideoJobNotFoundException: If job doesn't exist
            AuthorizationException: If user doesn't own the job
            InvalidJobStatusException: If job is not completed
            StorageException: If ZIP file is not accessible
        """
        try:
            job = await self._get_authorized_job(request.job_id, request.user_id)

            self._validate_job_for_download(job)

            await self._validate_file_availability(job)

            file_size = await self._get_safe_file_size(job.zip_file_path)

            filename = self._generate_download_filename(job)

            metadata = self._prepare_metadata(job) if request.include_metadata else None

            await self._update_job_download_stats(job)

            return DownloadResultResponse(
                success=True,
                file_path=job.zip_file_path,
                file_size=file_size,
                filename=filename,
                content_type="application/zip",
                job_data=self._create_download_job_data(job),
                metadata=metadata
            )

        except (VideoJobNotFoundException, AuthorizationException, InvalidJobStatusException, StorageException):
            raise
        except Exception as e:
            print(f"Unexpected error in DownloadProcessingResultUseCase: {str(e)}")
            raise StorageException("download", request.job_id, f"Download preparation failed: {str(e)}")

    async def _get_authorized_job(self, job_id: str, user_id: str) -> VideoJob:
        """
        Retrieve job and verify user authorization.

        Args:
            job_id: ID of the job to retrieve
            user_id: ID of the requesting user

        Returns:
            VideoJob: Retrieved job entity

        Raises:
            VideoJobNotFoundException: If job doesn't exist
            AuthorizationException: If user doesn't own the job
        """
        try:
            job = await self.job_repository.find_user_job_by_id(job_id, user_id)

            if not job:
                existing_job = await self.job_repository.find_by_id(job_id)
                if existing_job:
                    raise AuthorizationException(user_id, job_id)
                else:
                    raise VideoJobNotFoundException(job_id)

            return job

        except (AuthorizationException, VideoJobNotFoundException):
            raise
        except Exception as e:
            print(f"Error retrieving job {job_id}: {str(e)}")
            raise VideoJobNotFoundException(job_id)

    def _validate_job_for_download(self, job: VideoJob) -> None:
        """
        Validate that the job is in a state that allows downloading.

        Args:
            job: Video job to validate

        Raises:
            InvalidJobStatusException: If job is not completed successfully
        """
        from domain.entities.video_job import JobStatus

        if job.status != JobStatus.COMPLETED:
            raise InvalidJobStatusException(
                job.id,
                job.status.value,
                "completed"
            )

        if not job.zip_file_path:
            raise StorageException(
                "download",
                job.id,
                "ZIP file path not available"
            )

    async def _validate_file_availability(self, job: VideoJob) -> None:
        """
        Validate that the ZIP file exists and is accessible.

        Args:
            job: Video job with ZIP file to validate

        Raises:
            StorageException: If ZIP file is not accessible
        """
        if not job.zip_file_path:
            raise StorageException(
                "access",
                job.id,
                "ZIP file path not set"
            )

        if not os.path.exists(job.zip_file_path):
            raise StorageException(
                "access",
                job.zip_file_path,
                "ZIP file not found on storage"
            )

        if not os.path.isfile(job.zip_file_path):
            raise StorageException(
                "access",
                job.zip_file_path,
                "ZIP file path exists but is not a file"
            )

    async def _get_safe_file_size(self, file_path: str) -> int:
        """
        Get file size with comprehensive error handling.

        Args:
            file_path: Path to the file

        Returns:
            int: File size in bytes
        """
        try:
            if hasattr(self.file_storage, 'get_file_size'):
                return await self.file_storage.get_file_size(file_path)
            else:
                return os.path.getsize(file_path) if os.path.exists(file_path) else 0
        except Exception as e:
            print(f"Error getting file size for {file_path}: {str(e)}")
            try:
                return os.path.getsize(file_path) if os.path.exists(file_path) else 0
            except Exception:
                return 0

    def _generate_download_filename(self, job: VideoJob) -> str:
        """
        Generate a user-friendly filename for download.

        Args:
            job: Video job to generate filename for

        Returns:
            str: Generated filename for download
        """
        try:
            base_name = os.path.splitext(job.original_filename)[0] if job.original_filename else job.id
            timestamp = job.processing_completed_at.strftime("%Y%m%d_%H%M%S") if job.processing_completed_at else "unknown"
            return f"{base_name}_frames_{timestamp}.zip"
        except Exception:
            return f"{job.id}_frames.zip"

    def _prepare_metadata(self, job: VideoJob) -> Dict[str, Any]:
        """
        Prepare processing metadata for download.

        Args:
            job: Video job to extract metadata from

        Returns:
            Dict[str, Any]: Processing metadata
        """
        try:
            processing_duration = 0
            if job.processing_started_at and job.processing_completed_at:
                processing_duration = (job.processing_completed_at - job.processing_started_at).total_seconds()

            zip_size_mb = 0
            if job.zip_file_size:
                zip_size_mb = job.zip_file_size / (1024 * 1024)

            return {
                "processing_info": {
                    "original_filename": job.original_filename or "unknown",
                    "video_duration": job.duration or 0,
                    "video_frame_rate": job.frame_rate or 0,
                    "extraction_fps": job.extraction_fps or 0,
                    "frames_extracted": job.frame_count or 0,
                    "processing_duration": processing_duration,
                    "zip_size_mb": zip_size_mb
                },
                "job_info": {
                    "job_id": job.id,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "processing_started_at": job.processing_started_at.isoformat() if job.processing_started_at else None,
                    "processing_completed_at": job.processing_completed_at.isoformat() if job.processing_completed_at else None
                },
                "extraction_config": job.metadata.get("extraction_config", {}) if job.metadata else {}
            }
        except Exception as e:
            print(f"Error preparing metadata: {str(e)}")
            return {"error": "Metadata preparation failed"}

    async def _update_job_download_stats(self, job: VideoJob) -> None:
        """
        Update job statistics to track download activity.

        Args:
            job: Video job being downloaded
        """
        try:
            from datetime import datetime

            if not job.metadata:
                job.metadata = {}

            download_stats = job.metadata.get("download_stats", {})
            download_count = download_stats.get("count", 0) + 1

            job.metadata["download_stats"] = {
                "count": download_count,
                "last_downloaded_at": datetime.utcnow().isoformat(),
                "first_downloaded_at": download_stats.get("first_downloaded_at", datetime.utcnow().isoformat())
            }

            await self.job_repository.update(job)
        except Exception as e:
            print(f"Warning: Failed to update download stats: {str(e)}")

    def _create_download_job_data(self, job: VideoJob) -> Dict[str, Any]:
        """
        Create job data for download tracking.

        Args:
            job: Video job entity

        Returns:
            Dict[str, Any]: Job data for download response
        """
        try:
            file_size_mb = 0
            if job.file_size:
                file_size_mb = job.file_size / (1024 * 1024)

            zip_size_mb = 0
            if job.zip_file_size:
                zip_size_mb = job.zip_file_size / (1024 * 1024)

            return {
                "id": job.id,
                "original_filename": job.original_filename or "unknown",
                "file_size_mb": file_size_mb,
                "frame_count": job.frame_count or 0,
                "zip_size_mb": zip_size_mb,
                "processing_completed_at": job.processing_completed_at.isoformat() if job.processing_completed_at else None,
                "processing_duration": self._get_processing_duration(job)
            }
        except Exception as e:
            print(f"Error creating job data: {str(e)}")
            return {
                "id": job.id,
                "original_filename": "unknown",
                "file_size_mb": 0,
                "frame_count": 0,
                "zip_size_mb": 0,
                "processing_completed_at": None,
                "processing_duration": 0
            }

    def _get_processing_duration(self, job: VideoJob) -> float:
        """
        Calculate processing duration safely.

        Args:
            job: Video job entity

        Returns:
            float: Processing duration in seconds
        """
        try:
            if job.processing_started_at and job.processing_completed_at:
                return (job.processing_completed_at - job.processing_started_at).total_seconds()
            return 0.0
        except Exception:
            return 0.0


class DeleteVideoJobUseCase:
    """
    Use case for deleting video jobs and associated files.

    This use case handles requests for removing completed or failed jobs
    from the system, including cleanup of associated files and database records.
    """

    def __init__(self,
                 job_repository: VideoJobRepositoryInterface,
                 file_storage: FileStorageInterface):
        """
        Initialize the delete video job use case.

        Args:
            job_repository: Repository for video job data operations
            file_storage: Service for file storage operations
        """
        self.job_repository = job_repository
        self.file_storage = file_storage

    async def execute(self, request: DeleteJobRequest) -> DeleteJobResponse:
        """
        Execute the delete video job use case.

        Args:
            request: Delete request containing job and user information

        Returns:
            DeleteJobResponse: Result of the deletion operation

        Raises:
            VideoJobNotFoundException: If job doesn't exist
            AuthorizationException: If user doesn't own the job
            InvalidJobStatusException: If job cannot be deleted
        """
        try:
            job = await self._get_authorized_job(request.job_id, request.user_id)

            self._validate_job_for_deletion(job)

            files_deleted = []

            if request.delete_files:
                files_deleted = await self._cleanup_job_files(job)

            await self.job_repository.delete(job.id)

            return DeleteJobResponse(
                success=True,
                job_id=job.id,
                message="Job deleted successfully",
                files_deleted=files_deleted
            )

        except (VideoJobNotFoundException, AuthorizationException, InvalidJobStatusException):
            raise
        except Exception as e:
            print(f"Unexpected error in DeleteVideoJobUseCase: {str(e)}")
            raise StorageException("delete", request.job_id, f"Job deletion failed: {str(e)}")

    async def _get_authorized_job(self, job_id: str, user_id: str) -> VideoJob:
        """
        Retrieve job and verify user authorization.

        Args:
            job_id: ID of the job to retrieve
            user_id: ID of the requesting user

        Returns:
            VideoJob: Retrieved job entity

        Raises:
            VideoJobNotFoundException: If job doesn't exist
            AuthorizationException: If user doesn't own the job
        """
        try:
            job = await self.job_repository.find_user_job_by_id(job_id, user_id)

            if not job:
                existing_job = await self.job_repository.find_by_id(job_id)
                if existing_job:
                    raise AuthorizationException(user_id, job_id)
                else:
                    raise VideoJobNotFoundException(job_id)

            return job

        except (AuthorizationException, VideoJobNotFoundException):
            raise
        except Exception as e:
            print(f"Error retrieving job for deletion {job_id}: {str(e)}")
            raise VideoJobNotFoundException(job_id)

    def _validate_job_for_deletion(self, job: VideoJob) -> None:
        """
        Validate that the job can be safely deleted.

        Args:
            job: Video job to validate for deletion

        Raises:
            InvalidJobStatusException: If job is currently being processed
        """
        from domain.entities.video_job import JobStatus

        if job.status == JobStatus.PROCESSING:
            raise InvalidJobStatusException(
                job.id,
                job.status.value,
                "completed, failed, or cancelled"
            )

    async def _cleanup_job_files(self, job: VideoJob) -> list:
        """
        Clean up all files associated with the job.

        Args:
            job: Video job whose files should be cleaned up

        Returns:
            list: List of files that were successfully deleted
        """
        files_deleted = []

        if job.file_path and os.path.exists(job.file_path):
            try:
                if await self.file_storage.delete_file(job.file_path):
                    files_deleted.append(job.file_path)
            except Exception as e:
                print(f"Failed to delete video file {job.file_path}: {str(e)}")

        if job.zip_file_path and os.path.exists(job.zip_file_path):
            try:
                if await self.file_storage.delete_file(job.zip_file_path):
                    files_deleted.append(job.zip_file_path)
            except Exception as e:
                print(f"Failed to delete ZIP file {job.zip_file_path}: {str(e)}")

        return files_deleted