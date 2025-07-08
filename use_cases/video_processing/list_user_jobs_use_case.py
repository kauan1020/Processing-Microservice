from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from domain.entities.video_job import VideoJob, JobStatus
from interfaces.repositories.video_job_repository_interface import VideoJobRepositoryInterface


@dataclass
class ListUserJobsRequest:
    """
    Request data structure for listing user's jobs.

    Contains user identification and pagination parameters for
    retrieving a user's video processing jobs with filtering options.

    Attributes:
        user_id: ID of the user whose jobs to retrieve
        status_filter: Optional status filter for job listing
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

    Contains paginated list of user's jobs with summary information,
    pagination metadata, and user processing statistics.

    Attributes:
        success: Whether the request was successful
        jobs: List of job data dictionaries
        total_count: Total number of jobs for the user
        page_info: Pagination information dictionary
        statistics: User's job processing statistics
    """
    success: bool
    jobs: List[Dict[str, Any]]
    total_count: int
    page_info: Dict[str, Any]
    statistics: Dict[str, Any]


class ListUserJobsUseCase:
    """
    Use case for listing a user's video processing jobs.

    This use case handles requests for retrieving a user's job history
    with filtering capabilities, pagination support, and comprehensive
    statistics about their video processing activity.

    It provides efficient job listing with proper pagination, filtering
    by status, and aggregated statistics for user dashboard displays.
    The implementation uses optimized database queries to avoid loading
    unnecessary data and provides consistent pagination behavior.
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

        Retrieves user's jobs with optional status filtering and pagination.
        Also fetches comprehensive statistics about the user's processing activity.

        Args:
            request: List request containing user ID and pagination parameters

        Returns:
            ListUserJobsResponse: Paginated list of user's jobs with statistics
        """
        if request.status_filter:
            jobs = await self.job_repository.find_by_user_and_status(
                request.user_id,
                request.status_filter,
                request.skip,
                request.limit
            )
            total_count = await self.job_repository.count_by_user_and_status(
                request.user_id,
                request.status_filter
            )
        else:
            jobs = await self.job_repository.find_by_user_id(
                request.user_id,
                request.skip,
                request.limit
            )
            total_count = await self.job_repository.count_by_user_id(request.user_id)

        statistics = await self.job_repository.get_user_job_statistics(request.user_id)

        job_data_list = [self._create_job_summary(job) for job in jobs]

        page_info = self._create_pagination_info(request, total_count)

        return ListUserJobsResponse(
            success=True,
            jobs=job_data_list,
            total_count=total_count,
            page_info=page_info,
            statistics=statistics
        )

    def _create_job_summary(self, job: VideoJob) -> Dict[str, Any]:
        """
        Create summary job data for list display.

        Transforms a VideoJob entity into a dictionary containing
        essential information for client display including processing
        status, file information, and download availability.

        Args:
            job: Video job entity

        Returns:
            Dict[str, Any]: Summary job information for API response
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

    def _create_pagination_info(self, request: ListUserJobsRequest, total_count: int) -> Dict[str, Any]:
        """
        Create pagination information for the response.

        Calculates pagination metadata including current page position,
        navigation availability, and total page count based on the
        request parameters and total result count.

        Args:
            request: Original request with pagination parameters
            total_count: Total number of jobs matching the criteria

        Returns:
            Dict[str, Any]: Pagination metadata for client navigation
        """
        return {
            "skip": request.skip,
            "limit": request.limit,
            "has_next": (request.skip + request.limit) < total_count,
            "has_previous": request.skip > 0,
            "total_pages": (total_count + request.limit - 1) // request.limit,
            "current_page": (request.skip // request.limit) + 1
        }