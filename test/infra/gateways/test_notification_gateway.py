import pytest
from unittest.mock import Mock
from datetime import datetime

from infra.presenters.video_processing_presenter import VideoProcessingPresenter
from use_cases.video_processing.submit_video_use_case import SubmitVideoResponse
from use_cases.video_processing.get_job_status_use_case import (
    GetJobStatusResponse,
    ListUserJobsResponse
)
from use_cases.video_processing.download_result_use_case import (
    DownloadResultResponse,
    DeleteJobResponse
)


class TestVideoProcessingPresenter:

    @pytest.fixture
    def presenter(self):
        return VideoProcessingPresenter()

    def test_present_video_submission_success_should_format_response_correctly(self, presenter):
        response = SubmitVideoResponse(
            job_id="job-123",
            message="Video submitted successfully for processing",
            queue_position=5,
            estimated_processing_time=300.0,
            estimated_frames=100,
            job_data={
                "original_filename": "test_video.mp4",
                "file_size_mb": 10.5,
                "video_format": "mp4",
                "duration": 60.0,
                "extraction_fps": 1.0
            }
        )

        result = presenter.present_video_submission_success(response)

        assert result["success"] is True
        assert result["message"] == "Video submitted successfully for processing"
        assert result["data"]["job"]["id"] == "job-123"
        assert result["data"]["job"]["queue_position"] == 5
        assert result["data"]["job"]["estimated_processing_time_minutes"] == 5.0
        assert result["data"]["job"]["estimated_frames"] == 100
        assert result["data"]["video_info"]["original_filename"] == "test_video.mp4"
        assert result["data"]["video_info"]["file_size_mb"] == 10.5
        assert "timestamp" in result
        assert "links" in result

    def test_present_job_status_with_completed_job_should_include_download_links(self, presenter):
        job_data = {
            "id": "job-123",
            "status": "completed",
            "original_filename": "test_video.mp4",
            "file_size_mb": 10.5,
            "video_format": "mp4",
            "duration": 60.0,
            "frame_count": 100,
            "zip_size_mb": 5.2,
            "created_at": "2023-01-01T12:00:00",
            "processing_started_at": "2023-01-01T12:01:00",
            "processing_duration": 120.5
        }

        response = GetJobStatusResponse(
            success=True,
            job_data=job_data,
            status="completed",
            progress_percentage=100.0,
            estimated_completion=None,
            download_available=True
        )

        result = presenter.present_job_status(response)

        assert result["success"] is True
        assert result["data"]["job"]["id"] == "job-123"
        assert result["data"]["job"]["status"] == "completed"
        assert result["data"]["progress"]["percentage"] == 100.0
        assert result["data"]["results"]["download_available"] is True
        assert "links" in result
        assert result["links"]["download"] == "/video-processing/jobs/job-123/download"
        assert "timestamp" in result

    def test_present_job_status_with_failed_job_should_include_error_info(self, presenter):
        job_data = {
            "id": "job-123",
            "status": "failed",
            "original_filename": "test_video.mp4",
            "error_message": "Video format not supported",
            "updated_at": "2023-01-01T12:05:00"
        }

        response = GetJobStatusResponse(
            success=True,
            job_data=job_data,
            status="failed",
            progress_percentage=None,
            estimated_completion=None,
            download_available=False
        )

        result = presenter.present_job_status(response)

        assert result["data"]["error"]["message"] == "Video format not supported"
        assert result["data"]["error"]["failed_at"] == "2023-01-01T12:05:00"
        assert "links" not in result

    def test_present_job_status_with_processing_job_should_include_progress_info(self, presenter):
        job_data = {
            "id": "job-123",
            "status": "processing",
            "original_filename": "test_video.mp4",
            "processing_started_at": "2023-01-01T12:01:00",
            "processing_duration": 60.0
        }

        response = GetJobStatusResponse(
            success=True,
            job_data=job_data,
            status="processing",
            progress_percentage=75.0,
            estimated_completion="2023-01-01T12:05:00",
            download_available=False
        )

        result = presenter.present_job_status(response)

        assert result["data"]["progress"]["percentage"] == 75.0
        assert result["data"]["progress"]["estimated_completion"] == "2023-01-01T12:05:00"
        assert result["data"]["results"]["download_available"] is False

    def test_present_user_jobs_list_should_format_jobs_and_pagination(self, presenter):
        jobs = [
            {
                "id": "job-1",
                "original_filename": "video1.mp4",
                "status": "completed",
                "file_size_mb": 5.0,
                "video_format": "mp4",
                "frame_count": 60,
                "download_available": True,
                "created_at": "2023-01-01T10:00:00"
            },
            {
                "id": "job-2",
                "original_filename": "video2.avi",
                "status": "processing",
                "file_size_mb": 8.5,
                "video_format": "avi",
                "frame_count": None,
                "download_available": False,
                "created_at": "2023-01-01T11:00:00"
            }
        ]

        page_info = {
            "skip": 0,
            "limit": 20,
            "has_next": False,
            "has_previous": False,
            "total_pages": 1,
            "current_page": 1
        }

        statistics = {
            "total_jobs": 2,
            "completed_jobs": 1,
            "failed_jobs": 0,
            "pending_jobs": 0,
            "processing_jobs": 1,
            "total_frames_extracted": 60,
            "total_processing_time": 120.0
        }

        response = ListUserJobsResponse(
            success=True,
            jobs=jobs,
            total_count=2,
            page_info=page_info,
            statistics=statistics
        )

        result = presenter.present_user_jobs_list(response)

        assert result["success"] is True
        assert len(result["data"]["jobs"]) == 2

        # Check first job formatting
        job1 = result["data"]["jobs"][0]
        assert job1["id"] == "job-1"
        assert job1["download_available"] is True
        assert job1["download_url"] == "/video-processing/jobs/job-1/download"

        # Check second job formatting
        job2 = result["data"]["jobs"][1]
        assert job2["id"] == "job-2"
        assert job2["download_available"] is False
        assert "download_url" not in job2

        # Check pagination
        pagination = result["data"]["pagination"]
        assert pagination["total_count"] == 2
        assert pagination["skip"] == 0
        assert pagination["limit"] == 20
        assert pagination["current_page"] == 1

        # Check statistics
        stats = result["data"]["statistics"]
        assert stats["total_jobs"] == 2
        assert stats["completed_jobs"] == 1
        assert stats["success_rate"] == 50.0
        assert stats["total_processing_time_hours"] == 0.03

    def test_present_user_jobs_list_with_empty_list_should_handle_gracefully(self, presenter):
        response = ListUserJobsResponse(
            success=True,
            jobs=[],
            total_count=0,
            page_info={
                "skip": 0,
                "limit": 20,
                "has_next": False,
                "has_previous": False,
                "total_pages": 0
            },
            statistics={
                "total_jobs": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "pending_jobs": 0,
                "processing_jobs": 0,
                "total_frames_extracted": 0,
                "total_processing_time": 0.0
            }
        )

        result = presenter.present_user_jobs_list(response)

        assert result["success"] is True
        assert len(result["data"]["jobs"]) == 0
        assert result["data"]["statistics"]["success_rate"] == 0.0

    def test_present_download_info_should_format_download_details(self, presenter):
        response = DownloadResultResponse(
            success=True,
            file_path="/storage/results/job-123_frames.zip",
            file_size=5242880,  # 5MB
            filename="test_video_frames_20230101_120000.zip",
            content_type="application/zip",
            job_data={
                "id": "job-123",
                "original_filename": "test_video.mp4",
                "frame_count": 100,
                "processing_completed_at": "2023-01-01T12:05:00"
            },
            metadata={
                "processing_info": {
                    "processing_duration": 120.5,
                    "extraction_fps": 1.0
                }
            }
        )

        result = presenter.present_download_info(response)

        assert result["success"] is True
        assert result["data"]["download"]["filename"] == "test_video_frames_20230101_120000.zip"
        assert result["data"]["download"]["file_size_mb"] == 5.0
        assert result["data"]["download"]["content_type"] == "application/zip"
        assert result["data"]["download"]["job_info"]["id"] == "job-123"
        assert result["data"]["download"]["job_info"]["frame_count"] == 100
        assert result["metadata"] is not None
        assert "timestamp" in result

    def test_present_download_info_without_metadata_should_handle_gracefully(self, presenter):
        response = DownloadResultResponse(
            success=True,
            file_path="/storage/results/job-123_frames.zip",
            file_size=1024,
            filename="frames.zip",
            content_type="application/zip",
            job_data={"id": "job-123"}
        )

        result = presenter.present_download_info(response)

        assert result["success"] is True
        assert result["metadata"] is None

    def test_present_job_deletion_success_should_format_deletion_response(self, presenter):
        response = DeleteJobResponse(
            success=True,
            job_id="job-123",
            message="Job deleted successfully",
            files_deleted=[
                "/storage/videos/user123/job-123_video.mp4",
                "/storage/results/user123/job-123_frames.zip"
            ]
        )

        result = presenter.present_job_deletion_success(response)

        assert result["success"] is True
        assert result["message"] == "Job deleted successfully"
        assert result["data"]["deleted_job_id"] == "job-123"
        assert len(result["data"]["files_deleted"]) == 2
        assert result["data"]["cleanup_summary"]["files_removed_count"] == 2
        assert "timestamp" in result

    def test_present_invalid_video_format_error_should_include_format_suggestions(self, presenter):
        message = "File extension .txt is not supported"

        result = presenter.present_invalid_video_format_error(message)

        assert result["success"] is False
        assert result["error"]["type"] == "invalid_video_format"
        assert result["error"]["message"] == "The uploaded file format is not supported"
        assert result["error"]["details"] == message
        assert "MP4" in result["error"]["supported_formats"]
        assert "AVI" in result["error"]["supported_formats"]
        assert len(result["error"]["suggestions"]) > 0
        assert "timestamp" in result

    def test_present_storage_error_should_include_storage_suggestions(self, presenter):
        message = "Disk space insufficient"

        result = presenter.present_storage_error(message)

        assert result["success"] is False
        assert result["error"]["type"] == "storage_error"
        assert result["error"]["message"] == "File storage operation failed"
        assert result["error"]["details"] == message
        assert len(result["error"]["suggestions"]) > 0
        assert "Try uploading the file again" in result["error"]["suggestions"]

    def test_present_processing_error_should_include_processing_suggestions(self, presenter):
        message = "FFmpeg processing failed"

        result = presenter.present_processing_error(message)

        assert result["success"] is False
        assert result["error"]["type"] == "processing_error"
        assert result["error"]["message"] == "Video processing operation failed"
        assert result["error"]["details"] == message
        assert "Try with a different video file" in result["error"]["suggestions"]

    def test_present_job_not_found_error_should_include_job_suggestions(self, presenter):
        message = "Job with ID 'job-123' was not found"

        result = presenter.present_job_not_found_error(message)

        assert result["success"] is False
        assert result["error"]["type"] == "job_not_found"
        assert result["error"]["message"] == "The requested video processing job was not found"
        assert result["error"]["details"] == message
        assert "Check the job ID is correct" in result["error"]["suggestions"]

    def test_present_authorization_error_should_include_auth_suggestions(self, presenter):
        message = "User does not own this job"

        result = presenter.present_authorization_error(message)

        assert result["success"] is False
        assert result["error"]["type"] == "authorization_error"
        assert result["error"]["message"] == "You are not authorized to access this resource"
        assert result["error"]["details"] == message
        assert "Ensure you are logged in" in result["error"]["suggestions"]

    def test_present_invalid_job_status_error_should_include_status_suggestions(self, presenter):
        message = "Job is currently processing and cannot be deleted"

        result = presenter.present_invalid_job_status_error(message)

        assert result["success"] is False
        assert result["error"]["type"] == "invalid_job_status"
        assert result["error"]["message"] == "The job is not in the correct status for this operation"
        assert result["error"]["details"] == message
        assert "Wait for the job to complete" in result["error"]["suggestions"]

    def test_present_validation_error_should_include_validation_suggestions(self, presenter):
        message = "Invalid extraction_fps value: must be between 0.1 and 60"

        result = presenter.present_validation_error(message)

        assert result["success"] is False
        assert result["error"]["type"] == "validation_error"
        assert result["error"]["message"] == "Request validation failed"
        assert result["error"]["details"] == message
        assert "Check your request parameters" in result["error"]["suggestions"]

    def test_present_internal_server_error_should_include_error_id(self, presenter):
        message = "Unexpected database connection error"

        result = presenter.present_internal_server_error(message)

        assert result["success"] is False
        assert result["error"]["type"] == "internal_server_error"
        assert result["error"]["message"] == "An unexpected error occurred"
        assert result["error"]["details"] == "Please try again later or contact support if the problem persists"
        assert result["error"]["error_id"].startswith("err_")
        assert "Try the request again" in result["error"]["suggestions"]
        assert "timestamp" in result

    def test_all_error_presentations_should_have_consistent_structure(self, presenter):
        error_methods = [
            ("present_invalid_video_format_error", "Format error"),
            ("present_storage_error", "Storage error"),
            ("present_processing_error", "Processing error"),
            ("present_job_not_found_error", "Not found error"),
            ("present_authorization_error", "Auth error"),
            ("present_invalid_job_status_error", "Status error"),
            ("present_validation_error", "Validation error"),
            ("present_internal_server_error", "Internal error")
        ]

        for method_name, test_message in error_methods:
            method = getattr(presenter, method_name)
            result = method(test_message)

            # Check consistent structure
            assert "success" in result
            assert result["success"] is False
            assert "error" in result
            assert "type" in result["error"]
            assert "message" in result["error"]
            assert "details" in result["error"]
            assert "suggestions" in result["error"]
            assert "timestamp" in result
            assert isinstance(result["error"]["suggestions"], list)
            assert len(result["error"]["suggestions"]) > 0

    def test_success_presentations_should_have_consistent_structure(self, presenter):
        # Test submit video success
        submit_response = SubmitVideoResponse(
            job_id="job-123",
            message="Success",
            queue_position=1,
            estimated_processing_time=60.0,
            estimated_frames=30,
            job_data={"original_filename": "test.mp4"}
        )
        submit_result = presenter.present_video_submission_success(submit_response)

        # Test job status
        status_response = GetJobStatusResponse(
            success=True,
            job_data={"id": "job-123", "status": "completed"},
            status="completed",
            progress_percentage=100.0,
            estimated_completion=None,
            download_available=True
        )
        status_result = presenter.present_job_status(status_response)

        # Test download info
        download_response = DownloadResultResponse(
            success=True,
            file_path="/test/path",
            file_size=1024,
            filename="test.zip",
            content_type="application/zip",
            job_data={"id": "job-123"}
        )
        download_result = presenter.present_download_info(download_response)

        # Check all have consistent success structure
        for result in [submit_result, status_result, download_result]:
            assert "success" in result
            assert result["success"] is True
            assert "data" in result
            assert "timestamp" in result
            assert isinstance(result["timestamp"], str)