import pytest
from unittest.mock import Mock, AsyncMock
from fastapi import UploadFile, HTTPException

from infra.controllers.video_processing_controller import VideoProcessingController
from use_cases.video_processing.submit_video_use_case import (
    SubmitVideoProcessingUseCase,
    SubmitVideoResponse
)
from use_cases.video_processing.get_job_status_use_case import (
    GetJobStatusUseCase,
    GetJobStatusResponse,
    ListUserJobsUseCase,
    ListUserJobsResponse
)
from use_cases.video_processing.download_result_use_case import (
    DownloadProcessingResultUseCase,
    DownloadResultResponse,
    DeleteVideoJobUseCase,
    DeleteJobResponse
)
from domain.exceptions import (
    ProcessingException,
    InvalidVideoFormatException,
    VideoJobNotFoundException,
    AuthorizationException,
    InvalidJobStatusException,
    StorageException
)
from domain.entities.video_job import JobStatus


@pytest.fixture
def mock_submit_video_use_case():
    return Mock(spec=SubmitVideoProcessingUseCase)


@pytest.fixture
def mock_get_job_status_use_case():
    return Mock(spec=GetJobStatusUseCase)


@pytest.fixture
def mock_list_user_jobs_use_case():
    return Mock(spec=ListUserJobsUseCase)


@pytest.fixture
def mock_download_result_use_case():
    return Mock(spec=DownloadProcessingResultUseCase)


@pytest.fixture
def mock_delete_job_use_case():
    return Mock(spec=DeleteVideoJobUseCase)


@pytest.fixture
def mock_presenter():
    presenter = Mock()
    presenter.present_video_submission_success.return_value = {"success": True, "data": {"job_id": "test-job-id"}}
    presenter.present_job_status.return_value = {"success": True, "data": {"status": "completed"}}
    presenter.present_user_jobs_list.return_value = {"success": True, "data": {"jobs": []}}
    presenter.present_download_info.return_value = {"success": True, "data": {"file_path": "/test/path"}}
    presenter.present_job_deletion_success.return_value = {"success": True, "message": "Job deleted"}
    presenter.present_invalid_video_format_error.return_value = {"error": "Invalid format"}
    presenter.present_storage_error.return_value = {"error": "Storage error"}
    presenter.present_processing_error.return_value = {"error": "Processing error"}
    presenter.present_validation_error.return_value = {"error": "Validation error"}
    presenter.present_internal_server_error.return_value = {"error": "Internal error"}
    presenter.present_job_not_found_error.return_value = {"error": "Job not found"}
    presenter.present_authorization_error.return_value = {"error": "Authorization error"}
    presenter.present_invalid_job_status_error.return_value = {"error": "Invalid job status"}
    return presenter


@pytest.fixture
def controller(
    mock_submit_video_use_case,
    mock_get_job_status_use_case,
    mock_list_user_jobs_use_case,
    mock_download_result_use_case,
    mock_delete_job_use_case,
    mock_presenter
):
    return VideoProcessingController(
        submit_video_use_case=mock_submit_video_use_case,
        get_job_status_use_case=mock_get_job_status_use_case,
        list_user_jobs_use_case=mock_list_user_jobs_use_case,
        download_result_use_case=mock_download_result_use_case,
        delete_job_use_case=mock_delete_job_use_case,
        presenter=mock_presenter
    )


@pytest.fixture
def mock_upload_file():
    content = b"fake video content"
    file = Mock(spec=UploadFile)
    file.filename = "test_video.mp4"
    file.size = len(content)
    file.content_type = "video/mp4"
    file.read = AsyncMock(return_value=content)
    return file


class TestVideoProcessingController:

    @pytest.mark.asyncio
    async def test_submit_video_for_processing_with_valid_input_should_return_success_response(
        self, controller, mock_upload_file, mock_submit_video_use_case, mock_presenter
    ):
        mock_response = SubmitVideoResponse(
            job_id="test-job-id",
            message="Video submitted successfully",
            queue_position=1,
            estimated_processing_time=300.0,
            estimated_frames=100,
            job_data={}
        )
        mock_submit_video_use_case.execute = AsyncMock(return_value=mock_response)

        result = await controller.submit_video_for_processing(
            file=mock_upload_file,
            user_id="test-user",
            extraction_fps=2.0,
            output_format="png",
            quality=90
        )

        assert result == {"success": True, "data": {"job_id": "test-job-id"}}
        mock_submit_video_use_case.execute.assert_called_once()
        mock_presenter.present_video_submission_success.assert_called_once_with(mock_response)

    @pytest.mark.asyncio
    async def test_submit_video_for_processing_with_user_preferences_should_apply_preferences(
        self, controller, mock_upload_file, mock_submit_video_use_case
    ):
        user_preferences = {
            "processing": {
                "default_fps": 3.0,
                "default_quality": 85,
                "max_frames": 200
            }
        }

        mock_response = SubmitVideoResponse(
            job_id="test-job-id",
            message="Video submitted successfully",
            queue_position=1,
            estimated_processing_time=300.0,
            estimated_frames=100,
            job_data={}
        )
        mock_submit_video_use_case.execute = AsyncMock(return_value=mock_response)

        await controller.submit_video_for_processing(
            file=mock_upload_file,
            user_id="test-user",
            user_preferences=user_preferences
        )

        call_args = mock_submit_video_use_case.execute.call_args[0][0]
        assert call_args.extraction_fps == 3.0
        assert call_args.quality == 85

    @pytest.mark.asyncio
    async def test_submit_video_for_processing_with_invalid_video_format_should_raise_http_exception(
        self, controller, mock_submit_video_use_case, mock_presenter
    ):
        mock_upload_file = Mock(spec=UploadFile)
        mock_upload_file.filename = "test.txt"
        mock_upload_file.size = 1000
        mock_upload_file.content_type = "text/plain"

        with pytest.raises(HTTPException) as exc_info:
            await controller.submit_video_for_processing(
                file=mock_upload_file,
                user_id="test-user"
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_video_for_processing_with_oversized_file_should_raise_http_exception(
        self, controller
    ):
        mock_upload_file = Mock(spec=UploadFile)
        mock_upload_file.filename = "large_video.mp4"
        mock_upload_file.size = 600 * 1024 * 1024  # 600MB
        mock_upload_file.content_type = "video/mp4"

        with pytest.raises(HTTPException) as exc_info:
            await controller.submit_video_for_processing(
                file=mock_upload_file,
                user_id="test-user"
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_video_for_processing_with_invalid_video_format_exception_should_return_formatted_error(
        self, controller, mock_upload_file, mock_submit_video_use_case, mock_presenter
    ):
        mock_submit_video_use_case.execute = AsyncMock(
            side_effect=InvalidVideoFormatException("test.mp4", "Invalid format")
        )

        with pytest.raises(HTTPException) as exc_info:
            await controller.submit_video_for_processing(
                file=mock_upload_file,
                user_id="test-user"
            )

        assert exc_info.value.status_code == 400
        mock_presenter.present_invalid_video_format_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_video_for_processing_with_storage_exception_should_return_formatted_error(
        self, controller, mock_upload_file, mock_submit_video_use_case, mock_presenter
    ):
        mock_submit_video_use_case.execute = AsyncMock(
            side_effect=StorageException("store", "test.mp4", "Storage error")
        )

        with pytest.raises(HTTPException) as exc_info:
            await controller.submit_video_for_processing(
                file=mock_upload_file,
                user_id="test-user"
            )

        assert exc_info.value.status_code == 500
        mock_presenter.present_storage_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_video_for_processing_with_processing_exception_should_return_formatted_error(
        self, controller, mock_upload_file, mock_submit_video_use_case, mock_presenter
    ):
        mock_submit_video_use_case.execute = AsyncMock(
            side_effect=ProcessingException("Processing failed")
        )

        with pytest.raises(HTTPException) as exc_info:
            await controller.submit_video_for_processing(
                file=mock_upload_file,
                user_id="test-user"
            )

        assert exc_info.value.status_code == 500
        mock_presenter.present_processing_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_status_with_valid_input_should_return_success_response(
        self, controller, mock_get_job_status_use_case, mock_presenter
    ):
        mock_response = GetJobStatusResponse(
            success=True,
            job_data={"id": "test-job-id", "status": "completed"},
            status="completed",
            progress_percentage=100.0,
            estimated_completion=None,
            download_available=True
        )
        mock_get_job_status_use_case.execute = AsyncMock(return_value=mock_response)

        result = await controller.get_job_status("test-job-id", "test-user")

        assert result == {"success": True, "data": {"status": "completed"}}
        mock_get_job_status_use_case.execute.assert_called_once()
        mock_presenter.present_job_status.assert_called_once_with(mock_response)

    @pytest.mark.asyncio
    async def test_get_job_status_with_job_not_found_should_raise_http_exception(
        self, controller, mock_get_job_status_use_case, mock_presenter
    ):
        mock_get_job_status_use_case.execute = AsyncMock(
            side_effect=VideoJobNotFoundException("test-job-id")
        )

        with pytest.raises(HTTPException) as exc_info:
            await controller.get_job_status("test-job-id", "test-user")

        assert exc_info.value.status_code == 404
        mock_presenter.present_job_not_found_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_user_jobs_with_valid_input_should_return_success_response(
        self, controller, mock_list_user_jobs_use_case, mock_presenter
    ):
        mock_response = ListUserJobsResponse(
            success=True,
            jobs=[],
            total_count=0,
            page_info={"skip": 0, "limit": 20},
            statistics={}
        )
        mock_list_user_jobs_use_case.execute = AsyncMock(return_value=mock_response)

        result = await controller.list_user_jobs("test-user", skip=0, limit=20)

        assert result == {"success": True, "data": {"jobs": []}}
        mock_list_user_jobs_use_case.execute.assert_called_once()
        mock_presenter.present_user_jobs_list.assert_called_once_with(mock_response)

    @pytest.mark.asyncio
    async def test_list_user_jobs_with_status_filter_should_filter_by_status(
        self, controller, mock_list_user_jobs_use_case
    ):
        mock_response = ListUserJobsResponse(
            success=True,
            jobs=[],
            total_count=0,
            page_info={"skip": 0, "limit": 20},
            statistics={}
        )
        mock_list_user_jobs_use_case.execute = AsyncMock(return_value=mock_response)

        await controller.list_user_jobs("test-user", status_filter="completed")

        call_args = mock_list_user_jobs_use_case.execute.call_args[0][0]
        assert call_args.status_filter == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_download_processing_result_with_valid_input_should_return_success_response(
        self, controller, mock_download_result_use_case, mock_presenter
    ):
        mock_response = DownloadResultResponse(
            success=True,
            file_path="/test/path/result.zip",
            file_size=1024,
            filename="result.zip",
            content_type="application/zip",
            job_data={}
        )
        mock_download_result_use_case.execute = AsyncMock(return_value=mock_response)

        result = await controller.download_processing_result("test-job-id", "test-user")

        assert result == {"success": True, "data": {"file_path": "/test/path"}}
        mock_download_result_use_case.execute.assert_called_once()
        mock_presenter.present_download_info.assert_called_once_with(mock_response)

    @pytest.mark.asyncio
    async def test_download_processing_result_with_include_metadata_should_include_metadata(
        self, controller, mock_download_result_use_case
    ):
        mock_response = DownloadResultResponse(
            success=True,
            file_path="/test/path/result.zip",
            file_size=1024,
            filename="result.zip",
            content_type="application/zip",
            job_data={},
            metadata={"processing_time": 120}
        )
        mock_download_result_use_case.execute = AsyncMock(return_value=mock_response)

        await controller.download_processing_result(
            "test-job-id",
            "test-user",
            include_metadata=True
        )

        call_args = mock_download_result_use_case.execute.call_args[0][0]
        assert call_args.include_metadata is True

    @pytest.mark.asyncio
    async def test_download_processing_result_with_invalid_job_status_should_raise_http_exception(
        self, controller, mock_download_result_use_case, mock_presenter
    ):
        mock_download_result_use_case.execute = AsyncMock(
            side_effect=InvalidJobStatusException("test-job-id", "processing", "completed")
        )

        with pytest.raises(HTTPException) as exc_info:
            await controller.download_processing_result("test-job-id", "test-user")

        assert exc_info.value.status_code == 400
        mock_presenter.present_invalid_job_status_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_video_job_with_valid_input_should_return_success_response(
        self, controller, mock_delete_job_use_case, mock_presenter
    ):
        mock_response = DeleteJobResponse(
            success=True,
            job_id="test-job-id",
            message="Job deleted successfully",
            files_deleted=["/test/path/video.mp4", "/test/path/result.zip"]
        )
        mock_delete_job_use_case.execute = AsyncMock(return_value=mock_response)

        result = await controller.delete_video_job("test-job-id", "test-user")

        assert result == {"success": True, "message": "Job deleted"}
        mock_delete_job_use_case.execute.assert_called_once()
        mock_presenter.present_job_deletion_success.assert_called_once_with(mock_response)

    @pytest.mark.asyncio
    async def test_delete_video_job_with_delete_files_false_should_preserve_files(
        self, controller, mock_delete_job_use_case
    ):
        mock_response = DeleteJobResponse(
            success=True,
            job_id="test-job-id",
            message="Job deleted successfully",
            files_deleted=[]
        )
        mock_delete_job_use_case.execute = AsyncMock(return_value=mock_response)

        await controller.delete_video_job("test-job-id", "test-user", delete_files=False)

        call_args = mock_delete_job_use_case.execute.call_args[0][0]
        assert call_args.delete_files is False

    @pytest.mark.asyncio
    async def test_delete_video_job_with_unexpected_exception_should_raise_http_exception(
        self, controller, mock_delete_job_use_case, mock_presenter
    ):
        mock_delete_job_use_case.execute = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with pytest.raises(HTTPException) as exc_info:
            await controller.delete_video_job("test-job-id", "test-user")

        assert exc_info.value.status_code == 500
        mock_presenter.present_internal_server_error.assert_called_once()

    def test_validate_video_file_with_valid_file_should_not_raise_exception(self, controller):
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test_video.mp4"
        mock_file.size = 1024 * 1024  # 1MB
        mock_file.content_type = "video/mp4"

        controller._validate_video_file(mock_file)

    def test_validate_video_file_with_no_filename_should_raise_value_error(self, controller):
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = None

        with pytest.raises(ValueError, match="Filename is required"):
            controller._validate_video_file(mock_file)

    def test_validate_video_file_with_oversized_file_should_raise_value_error(self, controller):
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "large_video.mp4"
        mock_file.size = 600 * 1024 * 1024  # 600MB
        mock_file.content_type = "video/mp4"

        with pytest.raises(ValueError, match="File size exceeds maximum limit"):
            controller._validate_video_file(mock_file)

    def test_validate_video_file_with_unsupported_extension_should_raise_value_error(self, controller):
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "document.pdf"
        mock_file.size = 1024
        mock_file.content_type = "application/pdf"

        with pytest.raises(ValueError, match="Unsupported file format"):
            controller._validate_video_file(mock_file)

    def test_validate_video_file_with_invalid_content_type_should_raise_value_error(self, controller):
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test_video.mp4"
        mock_file.size = 1024
        mock_file.content_type = "text/plain"

        with pytest.raises(ValueError, match="File must be a video file"):
            controller._validate_video_file(mock_file)

    def test_validate_video_file_with_no_content_type_should_raise_value_error(self, controller):
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test_video.mp4"
        mock_file.size = 1024
        mock_file.content_type = None

        with pytest.raises(ValueError, match="File must be a video file"):
            controller._validate_video_file(mock_file)

    def test_validate_video_file_with_empty_filename_should_raise_value_error(self, controller):
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = ""
        mock_file.size = 1024
        mock_file.content_type = "video/mp4"

        with pytest.raises(ValueError, match="Filename is required"):
            controller._validate_video_file(mock_file)