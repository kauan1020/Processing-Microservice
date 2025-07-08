import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from use_cases.video_processing.submit_video_use_case import (
    SubmitVideoProcessingUseCase,
    SubmitVideoRequest,
    SubmitVideoResponse
)
from domain.entities.video_job import VideoJob, JobStatus, VideoFormat
from domain.value_objects import VideoFile, FrameExtractionConfig
from domain.exceptions import (
    ProcessingException,
    InvalidVideoFormatException,
    StorageException
)


class TestSubmitVideoProcessingUseCase:

    @pytest.fixture
    def mock_job_repository(self):
        repository = Mock()
        repository.create = AsyncMock()
        repository.count_by_status = AsyncMock(return_value=5)
        return repository

    @pytest.fixture
    def mock_video_processor(self):
        processor = Mock()
        processor.validate_video_file = AsyncMock(return_value=True)
        processor.get_video_info = AsyncMock(return_value={
            "duration": 60.0,
            "frame_rate": 30.0,
            "resolution": (1920, 1080),
            "codec": "h264"
        })
        processor.estimate_processing_time = AsyncMock(return_value=300.0)
        return processor

    @pytest.fixture
    def mock_file_storage(self):
        storage = Mock()
        storage.store_video_file = AsyncMock(return_value="/test/path/video.mp4")
        return storage

    @pytest.fixture
    def mock_kafka_gateway(self):
        gateway = Mock()
        gateway.publish_job_submitted = AsyncMock(return_value=True)
        return gateway

    @pytest.fixture
    def mock_user_service_gateway(self):
        gateway = Mock()
        gateway.verify_user_exists = AsyncMock(return_value=True)
        gateway.update_user_activity = AsyncMock(return_value=True)
        return gateway

    @pytest.fixture
    def use_case(self, mock_job_repository, mock_video_processor, mock_file_storage,
                 mock_kafka_gateway, mock_user_service_gateway):
        return SubmitVideoProcessingUseCase(
            job_repository=mock_job_repository,
            video_processor=mock_video_processor,
            file_storage=mock_file_storage,
            kafka_gateway=mock_kafka_gateway,
            user_service_gateway=mock_user_service_gateway
        )

    @pytest.fixture
    def valid_request(self):
        return SubmitVideoRequest(
            user_id="test-user-123",
            file_content=b"fake video content",
            original_filename="test_video.mp4",
            extraction_fps=1.0,
            output_format="png",
            quality=95
        )

    @pytest.fixture
    def mock_created_job(self):
        job = Mock()
        job.id = "job-123"
        job.original_filename = "test_video.mp4"
        job.get_file_size_mb = Mock(return_value=1.0)
        job.video_format = VideoFormat.MP4
        job.duration = 60.0
        job.extraction_fps = 1.0
        return job

    @pytest.mark.asyncio
    async def test_execute_with_valid_request_creates_job_successfully_and_returns_response_with_estimates(
            self, use_case, valid_request, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job

        with patch('os.path.exists', return_value=True):
            response = await use_case.execute(valid_request)

        assert isinstance(response, SubmitVideoResponse)
        assert response.job_id == "job-123"
        assert response.message == "Video submitted successfully for processing"
        assert response.queue_position == 6
        assert response.estimated_processing_time == 300.0

        mock_job_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_invalid_user_raises_processing_exception_with_user_not_found_message(
            self, use_case, valid_request, mock_user_service_gateway
    ):
        mock_user_service_gateway.verify_user_exists.return_value = False

        with pytest.raises(ProcessingException, match="User with ID 'test-user-123' not found"):
            await use_case.execute(valid_request)

    @pytest.mark.asyncio
    async def test_execute_with_invalid_video_format_raises_invalid_video_format_exception(
            self, use_case, valid_request, mock_video_processor
    ):
        mock_video_processor.validate_video_file.return_value = False

        with patch('os.path.exists', return_value=True):
            with pytest.raises(InvalidVideoFormatException):
                await use_case.execute(valid_request)

    @pytest.mark.asyncio
    async def test_execute_with_storage_failure_raises_storage_exception_with_error_details(
            self, use_case, valid_request, mock_file_storage
    ):
        mock_file_storage.store_video_file.side_effect = Exception("Storage failed")

        with pytest.raises(StorageException):
            await use_case.execute(valid_request)

    @pytest.mark.asyncio
    async def test_execute_publishes_job_submitted_event_to_kafka_with_correct_job_data(
            self, use_case, valid_request, mock_kafka_gateway, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job

        with patch('os.path.exists', return_value=True):
            await use_case.execute(valid_request)

        mock_kafka_gateway.publish_job_submitted.assert_called_once_with(mock_created_job)

    @pytest.mark.asyncio
    async def test_execute_updates_user_activity_with_submission_details(
            self, use_case, valid_request, mock_user_service_gateway, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job

        with patch('os.path.exists', return_value=True):
            await use_case.execute(valid_request)

        mock_user_service_gateway.update_user_activity.assert_called_once_with(
            "test-user-123",
            {
                "action": "video_submitted",
                "job_id": "job-123",
                "filename": "test_video.mp4",
                "file_size_mb": 1.0
            }
        )

    @pytest.mark.asyncio
    async def test_execute_with_video_validation_failure_handles_gracefully_and_raises_processing_exception(
            self, use_case, valid_request, mock_video_processor
    ):
        mock_video_processor.get_video_info.side_effect = Exception("Video analysis failed")

        with patch('os.path.exists', return_value=True):
            with pytest.raises(ProcessingException, match="Video metadata extraction failed"):
                await use_case.execute(valid_request)

    @pytest.mark.asyncio
    async def test_execute_stores_video_file_with_correct_parameters_and_user_organization(
            self, use_case, valid_request, mock_file_storage, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job

        with patch('os.path.exists', return_value=True):
            await use_case.execute(valid_request)

        mock_file_storage.store_video_file.assert_called_once_with(
            file_content=b"fake video content",
            filename="test_video.mp4",
            user_id="test-user-123"
        )

    @pytest.mark.asyncio
    async def test_execute_validates_video_file_format_through_processor_service(
            self, use_case, valid_request, mock_video_processor, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job

        with patch('os.path.exists', return_value=True):
            await use_case.execute(valid_request)

        mock_video_processor.validate_video_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_extracts_video_metadata_for_job_configuration(
            self, use_case, valid_request, mock_video_processor, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job

        with patch('os.path.exists', return_value=True):
            await use_case.execute(valid_request)

        mock_video_processor.get_video_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_estimates_processing_time_for_user_feedback(
            self, use_case, valid_request, mock_video_processor, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job

        with patch('os.path.exists', return_value=True):
            await use_case.execute(valid_request)

        mock_video_processor.estimate_processing_time.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_kafka_publish_failure_continues_job_creation_successfully(
            self, use_case, valid_request, mock_kafka_gateway, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job
        mock_kafka_gateway.publish_job_submitted.return_value = False

        with patch('os.path.exists', return_value=True):
            response = await use_case.execute(valid_request)

        assert response.job_id == "job-123"
        assert response.message == "Video submitted successfully for processing"

    @pytest.mark.asyncio
    async def test_execute_with_user_activity_update_failure_continues_job_creation_successfully(
            self, use_case, valid_request, mock_user_service_gateway, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job
        mock_user_service_gateway.update_user_activity.side_effect = Exception("Activity update failed")

        with patch('os.path.exists', return_value=True):
            response = await use_case.execute(valid_request)

        assert response.job_id == "job-123"
        assert response.message == "Video submitted successfully for processing"

    @pytest.mark.asyncio
    async def test_execute_creates_job_with_correct_extraction_config_parameters(
            self, use_case, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job

        request = SubmitVideoRequest(
            user_id="test-user-123",
            file_content=b"fake video content",
            original_filename="test_video.mp4",
            extraction_fps=2.0,
            output_format="jpg",
            quality=85,
            start_time=10.0,
            end_time=50.0,
            max_frames=100
        )

        with patch('os.path.exists', return_value=True):
            await use_case.execute(request)

        mock_job_repository.create.assert_called_once()
        created_job_call = mock_job_repository.create.call_args[0][0]

        assert created_job_call.extraction_fps == 2.0
        assert created_job_call.metadata["extraction_config"]["output_format"] == "jpg"
        assert created_job_call.metadata["extraction_config"]["quality"] == 85
        assert created_job_call.metadata["extraction_config"]["start_time"] == 10.0
        assert created_job_call.metadata["extraction_config"]["end_time"] == 50.0
        assert created_job_call.metadata["extraction_config"]["max_frames"] == 100

    @pytest.mark.asyncio
    async def test_execute_calculates_queue_position_based_on_pending_jobs_count(
            self, use_case, valid_request, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job
        mock_job_repository.count_by_status.return_value = 10

        with patch('os.path.exists', return_value=True):
            response = await use_case.execute(valid_request)

        assert response.queue_position == 11
        mock_job_repository.count_by_status.assert_called_once_with(JobStatus.PENDING)

    @pytest.mark.asyncio
    async def test_execute_handles_queue_position_calculation_failure_gracefully_with_fallback(
            self, use_case, valid_request, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job
        mock_job_repository.count_by_status.side_effect = Exception("Database error")

        with patch('os.path.exists', return_value=True):
            response = await use_case.execute(valid_request)

        assert response.queue_position == 1


    @pytest.mark.asyncio
    async def test_execute_validates_user_exists_before_processing_video(
            self, use_case, valid_request, mock_user_service_gateway, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job

        with patch('os.path.exists', return_value=True):
            await use_case.execute(valid_request)

        mock_user_service_gateway.verify_user_exists.assert_called_once_with("test-user-123")

    @pytest.mark.asyncio
    async def test_execute_handles_user_validation_service_failure_with_processing_exception(
            self, use_case, valid_request, mock_user_service_gateway
    ):
        mock_user_service_gateway.verify_user_exists.side_effect = Exception("User service unavailable")

        with pytest.raises(ProcessingException, match="User validation failed"):
            await use_case.execute(valid_request)

    @pytest.mark.asyncio
    async def test_execute_creates_job_with_pending_status_and_correct_timestamps(
            self, use_case, valid_request, mock_job_repository, mock_created_job
    ):
        mock_job_repository.create.return_value = mock_created_job

        with patch('os.path.exists', return_value=True):
            await use_case.execute(valid_request)

        created_job_call = mock_job_repository.create.call_args[0][0]

        assert created_job_call.status == JobStatus.PENDING
        assert created_job_call.user_id == "test-user-123"
        assert created_job_call.original_filename == "test_video.mp4"
        assert created_job_call.created_at is not None
        assert created_job_call.updated_at is not None

    @pytest.mark.asyncio
    async def test_execute_includes_video_metadata_in_job_metadata_for_processing_reference(
            self, use_case, valid_request, mock_job_repository, mock_created_job, mock_video_processor
    ):
        mock_job_repository.create.return_value = mock_created_job
        mock_video_processor.get_video_info.return_value = {
            "duration": 60.0,
            "frame_rate": 30.0,
            "resolution": (1920, 1080),
            "codec": "h264"
        }

        with patch('os.path.exists', return_value=True):
            await use_case.execute(valid_request)

        created_job_call = mock_job_repository.create.call_args[0][0]

        assert "video_info" in created_job_call.metadata
        assert created_job_call.metadata["video_info"]["duration"] == 60.0
        assert created_job_call.metadata["video_info"]["frame_rate"] == 30.0
        assert created_job_call.metadata["video_info"]["resolution"] == (1920, 1080)
        assert created_job_call.metadata["video_info"]["codec"] == "h264"