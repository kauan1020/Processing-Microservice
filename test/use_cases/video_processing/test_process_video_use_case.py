import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from datetime import datetime
from contextlib import contextmanager
import io

from use_cases.video_processing.process_video_use_case import (
    ProcessVideoUseCase,
    ProcessVideoRequest,
    ProcessVideoResponse
)
from domain.entities.video_job import JobStatus
from domain.exceptions import ProcessingException


class TestProcessVideoUseCase:

    @pytest.fixture
    def mock_job_repository(self):
        repository = Mock()
        repository.find_by_id = AsyncMock()
        repository.update = AsyncMock()
        return repository

    @pytest.fixture
    def mock_video_processor(self):
        processor = Mock()
        processor.extract_frames = AsyncMock(return_value=["/test/frame1.png", "/test/frame2.png"])
        return processor

    @pytest.fixture
    def mock_file_storage(self):
        storage = Mock()
        storage.store_file = AsyncMock(return_value="/test/result.zip")
        storage.store_video_file = AsyncMock(return_value="/test/result.zip")
        return storage

    @pytest.fixture
    def mock_notification_gateway(self):
        gateway = Mock()
        gateway.send_job_completion_notification = AsyncMock(return_value=True)
        gateway.send_job_failure_notification = AsyncMock(return_value=True)
        return gateway

    @pytest.fixture
    def mock_user_service_gateway(self):
        gateway = Mock()
        gateway.get_user_info = AsyncMock(return_value={
            "id": "test-user-123",
            "email": "test@example.com"
        })
        return gateway

    @pytest.fixture
    def mock_video_job(self):
        job = Mock()
        job.id = "job-123"
        job.user_id = "test-user-123"
        job.original_filename = "test_video.mp4"
        job.file_path = "/test/video.mp4"
        job.file_size = 1024 * 1024
        job.status = JobStatus.PENDING
        job.extraction_fps = 1.0
        job.frame_count = None
        job.zip_file_path = None
        job.zip_file_size = None
        job.error_message = None
        job.processing_started_at = None
        job.processing_completed_at = None
        job.metadata = {
            "extraction_config": {
                "output_format": "png",
                "quality": 95,
                "start_time": 0.0,
                "end_time": None,
                "max_frames": None
            }
        }
        job.get_file_size_mb = Mock(return_value=1.0)
        job.get_processing_duration = Mock(return_value=120.0)
        return job

    @pytest.fixture
    def use_case(self, mock_job_repository, mock_video_processor, mock_file_storage,
                 mock_notification_gateway, mock_user_service_gateway):
        return ProcessVideoUseCase(
            job_repository=mock_job_repository,
            video_processor=mock_video_processor,
            file_storage=mock_file_storage,
            notification_gateway=mock_notification_gateway,
            user_service_gateway=mock_user_service_gateway
        )

    @pytest.fixture
    def valid_request(self):
        return ProcessVideoRequest(
            job_id="job-123",
            worker_id="worker-456"
        )

    @contextmanager
    def mock_file_system_operations(self, frame_files=None):
        """Context manager for complete file system mocking"""
        frame_files = frame_files or ["frame1.png", "frame2.png"]

        # Create a mock file content for ZIP
        zip_content = b"fake zip file content"

        with patch('os.path.exists', return_value=True), \
                patch('os.path.dirname', return_value="/tmp/frames"), \
                patch('os.listdir', return_value=frame_files), \
                patch('os.path.join', side_effect=lambda *args: "/".join(args)), \
                patch('os.path.getsize', return_value=1024), \
                patch('os.makedirs'), \
                patch('shutil.rmtree'), \
                patch('shutil.move'), \
                patch('os.unlink'), \
                patch('tempfile.NamedTemporaryFile') as mock_temp_file, \
                patch('zipfile.ZipFile') as mock_zip, \
                patch('builtins.open', mock_open(read_data=zip_content)) as mock_file_open:
            # Configure temp file mock
            mock_temp_file.return_value.__enter__.return_value.name = "/tmp/test.zip"

            # Configure ZIP file mock
            mock_zip_instance = MagicMock()
            mock_zip.return_value.__enter__.return_value = mock_zip_instance
            mock_zip_instance.write = Mock()

            yield {
                'temp_file': mock_temp_file,
                'zip_file': mock_zip,
                'file_open': mock_file_open
            }

    @pytest.mark.asyncio
    async def test_execute_with_valid_pending_job_returns_successful_response(
            self, use_case, valid_request, mock_job_repository, mock_video_job
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job

        with self.mock_file_system_operations():
            response = await use_case.execute(valid_request)

        assert isinstance(response, ProcessVideoResponse)
        assert response.success is True
        assert response.job_id == "job-123"
        assert response.frame_count == 2
        assert response.processing_duration is not None

    @pytest.mark.asyncio
    async def test_execute_with_nonexistent_job_returns_failure_response_with_error_message(
            self, use_case, valid_request, mock_job_repository
    ):
        mock_job_repository.find_by_id.return_value = None

        response = await use_case.execute(valid_request)

        assert response.success is False
        assert "not found" in response.error_message
        assert response.job_id == "job-123"

    @pytest.mark.asyncio
    async def test_execute_with_processing_exception_returns_failure_response_with_error_details(
            self, use_case, valid_request, mock_job_repository, mock_video_job, mock_video_processor
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job
        mock_video_processor.extract_frames.side_effect = ProcessingException("Frame extraction failed")

        with patch('os.path.exists', return_value=True):
            response = await use_case.execute(valid_request)

        assert response.success is False
        assert "Frame extraction failed" in response.error_message
        assert response.job_id == "job-123"

    @pytest.mark.asyncio
    async def test_execute_updates_job_status_to_processing_with_worker_info_and_timestamp(
            self, use_case, valid_request, mock_job_repository, mock_video_job
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job

        with self.mock_file_system_operations(["frame1.png"]):
            await use_case.execute(valid_request)

        assert mock_video_job.status == JobStatus.COMPLETED
        assert mock_video_job.processing_started_at is not None
        assert mock_video_job.metadata["worker_id"] == "worker-456"
        assert mock_job_repository.update.called

    @pytest.mark.asyncio
    async def test_execute_sends_completion_notification_with_job_details_when_processing_succeeds(
            self, use_case, valid_request, mock_job_repository, mock_video_job, mock_notification_gateway
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job

        with self.mock_file_system_operations(["frame1.png"]):
            await use_case.execute(valid_request)

        mock_notification_gateway.send_job_completion_notification.assert_called_once()
        call_args = mock_notification_gateway.send_job_completion_notification.call_args[0][0]
        assert call_args["job_id"] == "job-123"
        assert call_args["user_email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_execute_sends_failure_notification_when_unexpected_exception_occurs(
            self, use_case, valid_request, mock_job_repository, mock_video_job,
            mock_notification_gateway, mock_video_processor
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job
        mock_video_processor.extract_frames.side_effect = Exception("Unexpected processing error")

        with patch('os.path.exists', return_value=True):
            await use_case.execute(valid_request)

        mock_notification_gateway.send_job_failure_notification.assert_called_once()
        call_args = mock_notification_gateway.send_job_failure_notification.call_args[0][0]
        assert call_args["job_id"] == "job-123"
        assert "Unexpected processing error" in call_args["error_message"]

    @pytest.mark.asyncio
    async def test_execute_updates_job_progress_multiple_times_during_processing_workflow(
            self, use_case, valid_request, mock_job_repository, mock_video_job
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job

        with self.mock_file_system_operations(["frame1.png"]):
            await use_case.execute(valid_request)

        assert mock_job_repository.update.call_count >= 3

    @pytest.mark.asyncio
    async def test_execute_handles_frame_extraction_returning_directory_path_correctly(
            self, use_case, valid_request, mock_job_repository, mock_video_job, mock_video_processor
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job
        mock_video_processor.extract_frames.return_value = "/tmp/frames_dir"

        with self.mock_file_system_operations():
            response = await use_case.execute(valid_request)

        assert response.success is True
        assert response.frame_count == 2

    @pytest.mark.asyncio
    async def test_execute_returns_failure_when_no_frames_extracted_from_video(
            self, use_case, valid_request, mock_job_repository, mock_video_job, mock_video_processor
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job
        mock_video_processor.extract_frames.return_value = []

        with patch('os.path.exists', return_value=True):
            response = await use_case.execute(valid_request)

        assert response.success is False
        assert "No frames extracted" in response.error_message

    @pytest.mark.asyncio
    async def test_execute_completes_job_with_correct_metadata_and_timestamps(
            self, use_case, valid_request, mock_job_repository, mock_video_job
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job

        with self.mock_file_system_operations():
            await use_case.execute(valid_request)

        assert mock_video_job.status == JobStatus.COMPLETED
        assert mock_video_job.frame_count == 2
        assert mock_video_job.zip_file_size == 1024
        assert mock_video_job.processing_completed_at is not None
        assert "processing_results" in mock_video_job.metadata

    @pytest.mark.asyncio
    async def test_execute_sets_job_to_failed_status_with_error_message_when_exception_occurs(
            self, use_case, valid_request, mock_job_repository, mock_video_job, mock_video_processor
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job
        mock_video_processor.extract_frames.side_effect = Exception("Processing failed")

        with patch('os.path.exists', return_value=True):
            await use_case.execute(valid_request)

        assert mock_video_job.status == JobStatus.FAILED
        assert "Processing failed" in mock_video_job.error_message
        assert mock_video_job.processing_completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_continues_processing_successfully_when_notification_service_fails(
            self, use_case, valid_request, mock_job_repository, mock_video_job,
            mock_notification_gateway, mock_user_service_gateway
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job
        mock_user_service_gateway.get_user_info.side_effect = Exception("User service unavailable")

        with self.mock_file_system_operations(["frame1.png"]):
            response = await use_case.execute(valid_request)

        assert response.success is True
        assert mock_video_job.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_skips_notification_when_user_has_example_email_address(
            self, use_case, valid_request, mock_job_repository, mock_video_job,
            mock_notification_gateway, mock_user_service_gateway
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job
        mock_user_service_gateway.get_user_info.return_value = {
            "id": "test-user-123",
            "email": "user_test-user-123@example.com"
        }

        with self.mock_file_system_operations(["frame1.png"]):
            await use_case.execute(valid_request)

        mock_notification_gateway.send_job_completion_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_returns_failure_when_zip_file_creation_fails(
            self, use_case, valid_request, mock_job_repository, mock_video_job
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job

        with patch('os.path.exists', return_value=True), \
                patch('os.path.dirname', return_value="/tmp/frames"), \
                patch('os.listdir', return_value=["frame1.png"]), \
                patch('zipfile.ZipFile', side_effect=Exception("ZIP creation failed")):
            response = await use_case.execute(valid_request)

        assert response.success is False
        assert "ZIP creation failed" in response.error_message

    @pytest.mark.asyncio
    async def test_execute_falls_back_to_local_storage_when_file_storage_service_fails(
            self, use_case, valid_request, mock_job_repository, mock_video_job, mock_file_storage
    ):
        mock_job_repository.find_by_id.return_value = mock_video_job
        mock_file_storage.store_file.side_effect = AttributeError("store_file not available")
        mock_file_storage.store_video_file.side_effect = Exception("Storage service failed")

        with patch('os.path.exists', return_value=True), \
                patch('os.path.dirname', return_value="/tmp/frames"), \
                patch('os.listdir', return_value=["frame1.png"]), \
                patch('os.path.join', side_effect=lambda *args: "/".join(args)), \
                patch('os.path.getsize', return_value=1024), \
                patch('os.makedirs'), \
                patch('shutil.rmtree'), \
                patch('shutil.move'), \
                patch('os.unlink'), \
                patch('tempfile.NamedTemporaryFile') as mock_temp_file, \
                patch('zipfile.ZipFile') as mock_zip, \
                patch('builtins.open', mock_open(read_data=b"fake zip content")):
            mock_temp_file.return_value.__enter__.return_value.name = "/tmp/test.zip"
            mock_zip_instance = MagicMock()
            mock_zip.return_value.__enter__.return_value = mock_zip_instance
            mock_zip_instance.write = Mock()

            response = await use_case.execute(valid_request)

        assert response.success is True
        assert "/app/storage/results/test-user-123" in mock_video_job.zip_file_path

    @pytest.mark.asyncio
    async def test_execute_handles_job_in_processing_status_successfully(
            self, use_case, valid_request, mock_job_repository, mock_video_job
    ):
        mock_video_job.status = JobStatus.PROCESSING
        mock_job_repository.find_by_id.return_value = mock_video_job

        with self.mock_file_system_operations(["frame1.png"]):
            response = await use_case.execute(valid_request)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_execute_rejects_job_when_status_is_completed(
            self, use_case, valid_request, mock_job_repository, mock_video_job
    ):
        mock_video_job.status = JobStatus.COMPLETED
        mock_job_repository.find_by_id.return_value = mock_video_job

        response = await use_case.execute(valid_request)

        assert response.success is False
        assert "not in a processable state" in response.error_message

    @pytest.mark.asyncio
    async def test_execute_rejects_job_when_status_is_failed(
            self, use_case, valid_request, mock_job_repository, mock_video_job
    ):
        mock_video_job.status = JobStatus.FAILED
        mock_job_repository.find_by_id.return_value = mock_video_job

        response = await use_case.execute(valid_request)

        assert response.success is False
        assert "not in a processable state" in response.error_message
