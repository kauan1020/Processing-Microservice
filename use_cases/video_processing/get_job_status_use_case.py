from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from domain.entities.video_job import VideoJob, JobStatus
from domain.exceptions import VideoJobNotFoundException, AuthorizationException
from interfaces.repositories.video_job_repository_interface import VideoJobRepositoryInterface


@dataclass
class GetJobStatusRequest:
    """
    Request data structure for getting job status information.

    Contains the job identifier and user information for retrieving
    job status and processing details.

    Attributes:
        job_id: ID of the video job to retrieve
        user_id: ID of the user requesting job status
    """
    job_id: str
    user_id: str


@dataclass
class GetJobStatusResponse:
    """
    Response data structure for job status retrieval.

    Contains comprehensive job status information including processing
    details, progress metrics, and file information.

    Attributes:
        success: Whether the request was successful
        job_data: Dictionary containing complete job information
        status: Current job status
        progress_percentage: Processing progress as percentage (0-100)
        estimated_completion: Estimated completion time if processing
        download_available: Whether ZIP file is ready for download
    """
    success: bool
    job_data: Dict[str, Any]
    status: str
    progress_percentage: Optional[float]
    estimated_completion: Optional[str]
    download_available: bool


@dataclass
class ListUserJobsRequest:
    """
    Request data structure for listing user's jobs.

    Contains user identification and pagination parameters for
    retrieving a user's video processing jobs.

    Attributes:
        user_id: ID of the user whose jobs to retrieve
        status_filter: Optional status filter
        skip: Number of jobs to skip for pagination
        limit: Maximum number of jobs to return
    """
    user_id: str
    status_filter: Optional[JobStatus] = None
    skip: int = 0
    limit: int = 20


@dataclass
class ListUserJobsResponse:
    """
    Response data structure for user jobs listing.

    Contains paginated list of user's jobs with summary information
    and pagination metadata.

    Attributes:
        success: Whether the request was successful
        jobs: List of job data dictionaries
        total_count: Total number of jobs for the user
        page_info: Pagination information
        statistics: User's job processing statistics
    """
    success: bool
    jobs: List[Dict[str, Any]]
    total_count: int
    page_info: Dict[str, Any]
    statistics: Dict[str, Any]


class GetJobStatusUseCase:
    """
    Use case for retrieving video job status and information.

    This use case handles requests for job status information, ensuring
    proper authorization and providing comprehensive job details including
    processing progress, completion status, and download availability.
    """

    def __init__(self, job_repository: VideoJobRepositoryInterface):
        """
        Initialize the get job status use case.

        Args:
            job_repository: Repository for video job data operations
        """
        self.job_repository = job_repository

    async def execute(self, request: GetJobStatusRequest) -> GetJobStatusResponse:
        """
        Execute the get job status use case.

        Args:
            request: Status request containing job and user identifiers

        Returns:
            GetJobStatusResponse: Job status information

        Raises:
            VideoJobNotFoundException: If job doesn't exist
            AuthorizationException: If user doesn't own the job
        """
        job = await self._get_authorized_job(request.job_id, request.user_id)

        progress_percentage = self._calculate_progress_percentage(job)
        estimated_completion = self._estimate_completion_time(job)
        download_available = job.is_completed() and job.zip_file_path is not None

        return GetJobStatusResponse(
            success=True,
            job_data=self._create_detailed_job_data(job),
            status=job.status.value,
            progress_percentage=progress_percentage,
            estimated_completion=estimated_completion,
            download_available=download_available
        )

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
        job = await self.job_repository.find_user_job_by_id(job_id, user_id)

        if not job:
            existing_job = await self.job_repository.find_by_id(job_id)
            if existing_job:
                raise AuthorizationException(user_id, job_id)
            else:
                raise VideoJobNotFoundException(job_id)

        return job

    def _calculate_progress_percentage(self, job: VideoJob) -> Optional[float]:
        """
        Calculate processing progress percentage based on job status.

        Args:
            job: Video job to calculate progress for

        Returns:
            Optional[float]: Progress percentage or None if not applicable
        """
        if job.is_pending():
            return 0.0
        elif job.is_processing():
            if job.duration and job.processing_started_at:
                from datetime import datetime
                elapsed = (datetime.utcnow() - job.processing_started_at).total_seconds()
                estimated_total = job.duration * 2
                return min(95.0, (elapsed / estimated_total) * 100)
            return 50.0
        elif job.is_completed():
            return 100.0
        elif job.is_failed() or job.is_cancelled():
            return None

        return None

    def _estimate_completion_time(self, job: VideoJob) -> Optional[str]:
        """
        Estimate job completion time based on current progress.

        Args:
            job: Video job to estimate completion for

        Returns:
            Optional[str]: Estimated completion time or None if not processing
        """
        if not job.is_processing() or not job.processing_started_at:
            return None

        from datetime import datetime, timedelta

        elapsed = (datetime.utcnow() - job.processing_started_at).total_seconds()

        if job.duration:
            estimated_total_time = job.duration * 2
            remaining_time = max(0, estimated_total_time - elapsed)
            completion_time = datetime.utcnow() + timedelta(seconds=remaining_time)
            return completion_time.isoformat()

        return None

    def _create_detailed_job_data(self, job: VideoJob) -> Dict[str, Any]:
        """
        Create comprehensive job data dictionary.

        Args:
            job: Video job entity

        Returns:
            Dict[str, Any]: Detailed job information
        """
        return {
            "id": job.id,
            "user_id": job.user_id,
            "original_filename": job.original_filename,
            "file_size_mb": job.get_file_size_mb(),
            "video_format": job.video_format.value,
            "duration": job.duration,
            "frame_rate": job.frame_rate,
            "extraction_fps": job.extraction_fps,
            "status": job.status.value,
            "frame_count": job.frame_count,
            "estimated_frames": job.get_estimated_frames(),
            "zip_file_path": job.zip_file_path,
            "zip_size_mb": job.get_zip_size_mb(),
            "error_message": job.error_message,
            "processing_duration": job.get_processing_duration(),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "processing_started_at": job.processing_started_at.isoformat() if job.processing_started_at else None,
            "processing_completed_at": job.processing_completed_at.isoformat() if job.processing_completed_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "metadata": job.metadata
        }


class ListUserJobsUseCase:
    """
    Use case for listing a user's video processing jobs.

    This use case handles requests for retrieving a user's job history
    with filtering, pagination, and summary statistics.
    """

    def __init__(self, job_repository: VideoJobRepositoryInterface):
        """
        Initialize the list user jobs use case.

        Args:
            job_repository: Repository for video job data operations
        """
        self.job_repository = job_repository

    async def execute(self, request: ListUserJobsRequest) -> ListUserJobsResponse:
        """
        Execute the list user jobs use case.

        Args:
            request: List request containing user ID and pagination parameters

        Returns:
            ListUserJobsResponse: Paginated list of user's jobs
        """
        if request.status_filter:
            jobs = await self.job_repository.find_by_status(
                request.status_filter,
                request.skip,
                request.limit
            )
            jobs = [job for job in jobs if job.user_id == request.user_id]
            total_count = await self.job_repository.count_by_status(request.status_filter)
        else:
            jobs = await self.job_repository.find_by_user_id(
                request.user_id,
                request.skip,
                request.limit
            )
            total_count = await self.job_repository.count_by_user_id(request.user_id)

        statistics = await self.job_repository.get_user_job_statistics(request.user_id)

        job_data_list = [self._create_summary_job_data(job) for job in jobs]

        return ListUserJobsResponse(
            success=True,
            jobs=job_data_list,
            total_count=total_count,
            page_info={
                "skip": request.skip,
                "limit": request.limit,
                "has_next": (request.skip + request.limit) < total_count,
                "has_previous": request.skip > 0,
                "total_pages": (total_count + request.limit - 1) // request.limit
            },
            statistics=statistics
        )

    def _create_summary_job_data(self, job: VideoJob) -> Dict[str, Any]:
        """
        Create summary job data for list display.

        Args:
            job: Video job entity

        Returns:
            Dict[str, Any]: Summary job information
        """
        return {
            "id": job.id,
            "original_filename": job.original_filename,
            "file_size_mb": job.get_file_size_mb(),
            "video_format": job.video_format.value,
            "duration": job.duration,
            "status": job.status.value,
            "frame_count": job.frame_count,
            "estimated_frames": job.get_estimated_frames(),
            "zip_size_mb": job.get_zip_size_mb(),
            "processing_duration": job.get_processing_duration(),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "processing_completed_at": job.processing_completed_at.isoformat() if job.processing_completed_at else None,
            "download_available": job.is_completed() and job.zip_file_path is not None
        }