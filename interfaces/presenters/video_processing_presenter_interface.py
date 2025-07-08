from abc import ABC, abstractmethod
from typing import Dict, Any

from use_cases.video_processing.submit_video_use_case import SubmitVideoResponse
from use_cases.video_processing.get_job_status_use_case import (
    GetJobStatusResponse,
    ListUserJobsResponse
)
from use_cases.video_processing.download_result_use_case import (
    DownloadResultResponse,
    DeleteJobResponse
)


class VideoProcessingPresenterInterface(ABC):
    """
    Presenter interface for formatting video processing responses.

    This interface defines the contract for presenting video processing
    data in various formats, handling success and error responses
    according to API design standards.

    The implementation should format responses consistently and
    provide appropriate error messages for different failure scenarios.
    """

    @abstractmethod
    def present_video_submission_success(self, response: SubmitVideoResponse) -> Dict[str, Any]:
        """
        Format successful video submission response.

        Args:
            response: Use case response with submission details

        Returns:
            Dict[str, Any]: Formatted success response
        """
        pass

    @abstractmethod
    def present_job_status(self, response: GetJobStatusResponse) -> Dict[str, Any]:
        """
        Format job status response.

        Args:
            response: Use case response with job status details

        Returns:
            Dict[str, Any]: Formatted job status response
        """
        pass

    @abstractmethod
    def present_user_jobs_list(self, response: ListUserJobsResponse) -> Dict[str, Any]:
        """
        Format user jobs list response.

        Args:
            response: Use case response with jobs list and pagination

        Returns:
            Dict[str, Any]: Formatted jobs list response
        """
        pass

    @abstractmethod
    def present_download_info(self, response: DownloadResultResponse) -> Dict[str, Any]:
        """
        Format download information response.

        Args:
            response: Use case response with download details

        Returns:
            Dict[str, Any]: Formatted download info response
        """
        pass

    @abstractmethod
    def present_job_deletion_success(self, response: DeleteJobResponse) -> Dict[str, Any]:
        """
        Format successful job deletion response.

        Args:
            response: Use case response with deletion details

        Returns:
            Dict[str, Any]: Formatted deletion success response
        """
        pass

    @abstractmethod
    def present_invalid_video_format_error(self, message: str) -> Dict[str, Any]:
        """
        Format invalid video format error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        pass

    @abstractmethod
    def present_storage_error(self, message: str) -> Dict[str, Any]:
        """
        Format storage-related error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        pass

    @abstractmethod
    def present_processing_error(self, message: str) -> Dict[str, Any]:
        """
        Format processing-related error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        pass

    @abstractmethod
    def present_job_not_found_error(self, message: str) -> Dict[str, Any]:
        """
        Format job not found error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        pass

    @abstractmethod
    def present_authorization_error(self, message: str) -> Dict[str, Any]:
        """
        Format authorization error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        pass

    @abstractmethod
    def present_invalid_job_status_error(self, message: str) -> Dict[str, Any]:
        """
        Format invalid job status error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        pass

    @abstractmethod
    def present_validation_error(self, message: str) -> Dict[str, Any]:
        """
        Format validation error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        pass

    @abstractmethod
    def present_internal_server_error(self, message: str) -> Dict[str, Any]:
        """
        Format internal server error response.

        Args:
            message: Error message

        Returns:
            Dict[str, Any]: Formatted error response
        """
        pass