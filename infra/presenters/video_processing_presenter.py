from typing import Dict, Any
from datetime import datetime

from interfaces.presenters.video_processing_presenter_interface import VideoProcessingPresenterInterface
from use_cases.video_processing.submit_video_use_case import SubmitVideoResponse
from use_cases.video_processing.get_job_status_use_case import (
    GetJobStatusResponse,
    ListUserJobsResponse
)
from use_cases.video_processing.download_result_use_case import (
    DownloadResultResponse,
    DeleteJobResponse
)


class VideoProcessingPresenter(VideoProcessingPresenterInterface):
    """
    Video processing presenter implementation for response formatting.

    This presenter provides concrete implementation for formatting video
    processing responses according to API standards with consistent
    structure, error handling, and user-friendly messaging.

    It transforms use case responses into properly formatted API responses
    with appropriate HTTP status codes, headers, and standardized error
    messages for consistent client experience across all endpoints.
    """

    def present_video_submission_success(self, response: SubmitVideoResponse) -> Dict[str, Any]:
        """
        Format successful video submission response.

        Args:
            response: Use case response with submission details

        Returns:
            Dict[str, Any]: Formatted success response
        """
        return {
            "success": True,
            "message": response.message,
            "data": {
                "job": {
                    "id": response.job_id,
                    "status": "pending",
                    "queue_position": response.queue_position,
                    "estimated_processing_time_minutes": round(response.estimated_processing_time / 60,
                                                               2) if response.estimated_processing_time else None,
                    "estimated_frames": response.estimated_frames,
                    "created_at": datetime.utcnow().isoformat()
                },
                "video_info": {
                    "original_filename": response.job_data.get("original_filename"),
                    "file_size_mb": response.job_data.get("file_size_mb"),
                    "video_format": response.job_data.get("video_format"),
                    "duration": response.job_data.get("duration"),
                    "extraction_fps": response.job_data.get("extraction_fps")
                }
            },
            "links": {
                "status": f"/video-processing/jobs/{response.job_id}/status",
                "cancel": f"/video-processing/jobs/{response.job_id}/cancel"
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def present_job_status(self, response: GetJobStatusResponse) -> Dict[str, Any]:
        """
        Format job status response.

        Args:
            response: Use case response with job status details

        Returns:
            Dict[str, Any]: Formatted job status response
        """
        job_data = response.job_data

        formatted_response = {
            "success": True,
            "data": {
                "job": {
                    "id": job_data.get("id"),
                    "status": response.status,
                    "original_filename": job_data.get("original_filename"),
                    "file_size_mb": job_data.get("file_size_mb"),
                    "video_format": job_data.get("video_format"),
                    "duration": job_data.get("duration"),
                    "extraction_fps": job_data.get("extraction_fps"),
                    "created_at": job_data.get("created_at"),
                    "updated_at": job_data.get("updated_at")
                },
                "progress": {
                    "percentage": response.progress_percentage,
                    "estimated_completion": response.estimated_completion,
                    "processing_started_at": job_data.get("processing_started_at"),
                    "processing_duration": job_data.get("processing_duration")
                },
                "results": {
                    "frame_count": job_data.get("frame_count"),
                    "estimated_frames": job_data.get("estimated_frames"),
                    "zip_size_mb": job_data.get("zip_size_mb"),
                    "download_available": response.download_available
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        if job_data.get("error_message"):
            formatted_response["data"]["error"] = {
                "message": job_data.get("error_message"),
                "failed_at": job_data.get("updated_at")
            }

        if response.download_available:
            formatted_response["links"] = {
                "download": f"/video-processing/jobs/{job_data.get('id')}/download",
                "frames": f"/video-processing/jobs/{job_data.get('id')}/frames"
            }

        return formatted_response

    def present_user_jobs_list(self, response: ListUserJobsResponse) -> Dict[str, Any]:
        """
        Format user jobs list response.

        Args:
            response: Use case response with jobs list and pagination

        Returns:
            Dict[str, Any]: Formatted jobs list response
        """
        formatted_jobs = []

        for job in response.jobs:
            formatted_job = {
                "id": job.get("id"),
                "original_filename": job.get("original_filename"),
                "status": job.get("status"),
                "file_size_mb": job.get("file_size_mb"),
                "video_format": job.get("video_format"),
                "duration": job.get("duration"),
                "frame_count": job.get("frame_count"),
                "estimated_frames": job.get("estimated_frames"),
                "zip_size_mb": job.get("zip_size_mb"),
                "processing_duration": job.get("processing_duration"),
                "created_at": job.get("created_at"),
                "processing_completed_at": job.get("processing_completed_at"),
                "download_available": job.get("download_available", False)
            }

            if job.get("download_available"):
                formatted_job["download_url"] = f"/video-processing/jobs/{job.get('id')}/download"

            formatted_jobs.append(formatted_job)

        # CORREÇÃO: Acessar page_info como dict, não como objeto
        page_info = response.page_info
        statistics = response.statistics

        return {
            "success": True,
            "data": {
                "jobs": formatted_jobs,
                "pagination": {
                    "total_count": response.total_count,
                    "skip": page_info.get("skip", 0),
                    "limit": page_info.get("limit", 20),
                    "has_next": page_info.get("has_next", False),
                    "has_previous": page_info.get("has_previous", False),
                    "total_pages": page_info.get("total_pages", 1),
                    "current_page": page_info.get("current_page", 1)
                },
                "statistics": {
                    "total_jobs": statistics.get("total_jobs", 0),
                    "completed_jobs": statistics.get("completed_jobs", 0),
                    "failed_jobs": statistics.get("failed_jobs", 0),
                    "pending_jobs": statistics.get("pending_jobs", 0),
                    "processing_jobs": statistics.get("processing_jobs", 0),
                    "total_frames_extracted": statistics.get("total_frames_extracted", 0),
                    "total_processing_time_hours": round(statistics.get("total_processing_time", 0) / 3600, 2),
                    "success_rate": round(
                        (statistics.get("completed_jobs", 0) / statistics.get("total_jobs", 1) * 100)
                        if statistics.get("total_jobs", 0) > 0 else 0, 2
                    )
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def present_download_info(self, response: DownloadResultResponse) -> Dict[str, Any]:
        """
        Format download information response.

        Args:
            response: Use case response with download details

        Returns:
            Dict[str, Any]: Formatted download info response
        """
        return {
            "success": True,
            "data": {
                "download": {
                    "filename": response.filename,
                    "file_size_mb": round(response.file_size / (1024 * 1024), 2),
                    "content_type": response.content_type,
                    "job_info": {
                        "id": response.job_data.get("id"),
                        "original_filename": response.job_data.get("original_filename"),
                        "frame_count": response.job_data.get("frame_count"),
                        "processing_completed_at": response.job_data.get("processing_completed_at")
                    }
                }
            },
            "metadata": response.metadata if response.metadata else None,
            "timestamp": datetime.utcnow().isoformat()
        }

    def present_job_deletion_success(self, response: DeleteJobResponse) -> Dict[str, Any]:
        """
        Format successful job deletion response.

        Args:
            response: Use case response with deletion details

        Returns:
            Dict[str, Any]: Formatted deletion success response
        """
        return {
            "success": True,
            "message": response.message,
            "data": {
                "deleted_job_id": response.job_id,
                "files_deleted": response.files_deleted,
                "cleanup_summary": {
                    "files_removed_count": len(response.files_deleted),
                    "storage_freed_mb": 0
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def present_invalid_video_format_error(self, message: str) -> Dict[str, Any]:
        """
        Format invalid video format error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        return {
            "success": False,
            "error": {
                "type": "invalid_video_format",
                "message": "The uploaded file format is not supported",
                "details": message,
                "supported_formats": ["MP4", "AVI", "MOV", "MKV", "WebM", "WMV", "FLV"],
                "suggestions": [
                    "Convert your video to MP4 format",
                    "Ensure the file is a valid video file",
                    "Check that the file extension matches the actual format"
                ]
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def present_storage_error(self, message: str) -> Dict[str, Any]:
        """
        Format storage-related error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        return {
            "success": False,
            "error": {
                "type": "storage_error",
                "message": "File storage operation failed",
                "details": message,
                "suggestions": [
                    "Try uploading the file again",
                    "Check your internet connection",
                    "Ensure the file is not corrupted"
                ]
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def present_processing_error(self, message: str) -> Dict[str, Any]:
        """
        Format processing-related error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        return {
            "success": False,
            "error": {
                "type": "processing_error",
                "message": "Video processing operation failed",
                "details": message,
                "suggestions": [
                    "Try with a different video file",
                    "Ensure the video is not corrupted",
                    "Contact support if the problem persists"
                ]
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def present_job_not_found_error(self, message: str) -> Dict[str, Any]:
        """
        Format job not found error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        return {
            "success": False,
            "error": {
                "type": "job_not_found",
                "message": "The requested video processing job was not found",
                "details": message,
                "suggestions": [
                    "Check the job ID is correct",
                    "Ensure you have access to this job",
                    "The job may have been deleted"
                ]
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def present_authorization_error(self, message: str) -> Dict[str, Any]:
        """
        Format authorization error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        return {
            "success": False,
            "error": {
                "type": "authorization_error",
                "message": "You are not authorized to access this resource",
                "details": message,
                "suggestions": [
                    "Ensure you are logged in",
                    "Check that you own this job",
                    "Verify your access permissions"
                ]
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def present_invalid_job_status_error(self, message: str) -> Dict[str, Any]:
        """
        Format invalid job status error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        return {
            "success": False,
            "error": {
                "type": "invalid_job_status",
                "message": "The job is not in the correct status for this operation",
                "details": message,
                "suggestions": [
                    "Wait for the job to complete",
                    "Check the current job status",
                    "Some operations are only available for completed jobs"
                ]
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def present_validation_error(self, message: str) -> Dict[str, Any]:
        """
        Format validation error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        return {
            "success": False,
            "error": {
                "type": "validation_error",
                "message": "Request validation failed",
                "details": message,
                "suggestions": [
                    "Check your request parameters",
                    "Ensure all required fields are provided",
                    "Verify parameter formats and values"
                ]
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def present_internal_server_error(self, message: str) -> Dict[str, Any]:
        """
        Format internal server error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        return {
            "success": False,
            "error": {
                "type": "internal_server_error",
                "message": "An unexpected error occurred",
                "details": "Please try again later or contact support if the problem persists",
                "error_id": f"err_{int(datetime.utcnow().timestamp())}",
                "suggestions": [
                    "Try the request again",
                    "Wait a few minutes and retry",
                    "Contact support with the error ID if the problem persists"
                ]
            },
            "timestamp": datetime.utcnow().isoformat()
        }