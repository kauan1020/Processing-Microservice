import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from use_cases.video_processing.get_job_status_use_case import (
    GetJobStatusUseCase,
    GetJobStatusRequest,
    GetJobStatusResponse
)
from domain.entities.video_job import JobStatus
from domain.exceptions import VideoJobNotFoundException, AuthorizationException


class TestGetJobStatusUseCase:

    @pytest.fixture
    def mock_job_repository(self):
        repository = Mock()
        repository.find_user_job_by_id = AsyncMock()
        repository.find_by_id = AsyncMock()
        return repository

    @pytest.fixture
    def use_case(self, mock_job_repository):
        return GetJobStatusUseCase(job_repository=mock_job_repository)

    @pytest.fixture
    def valid_request(self):
        return GetJobStatusRequest(
            job_id="job-123",
            user_id="test-user-123"
        )

    @pytest.fixture
    def mock_completed_job(self):
        job = Mock()
        job.id = "job-123"
        job.user_id = "test-user-123"
        job.status = JobStatus.COMPLETED
        job.original_filename = "test_video.mp4"
        job.frame_count = 60
        job.zip_file_path = "/test/result.zip"
        job.processing_completed_at = datetime.utcnow()
        job.is_completed = Mock(return_value=True)
        job.is_pending = Mock(return_value=False)
        job.is_processing = Mock(return_value=False)
        job.is_failed = Mock(return_value=False)
        job.is_cancelled = Mock(return_value=False)
        return job

    @pytest.fixture
    def mock_processing_job(self):
        job = Mock()
        job.id = "job-123"
        job.user_id = "test-user-123"
        job.status = JobStatus.PROCESSING
        job.processing_started_at = datetime.utcnow()
        job.duration = 60.0
        job.zip_file_path = None
        job.is_completed = Mock(return_value=False)
        job.is_pending = Mock(return_value=False)
        job.is_processing = Mock(return_value=True)
        job.is_failed = Mock(return_value=False)
        job.is_cancelled = Mock(return_value=False)
        return job

    @pytest.mark.asyncio
    async def test_execute_with_existing_job_should_return_status(
            self, use_case, valid_request, mock_job_repository, mock_completed_job
    ):
        mock_job_repository.find_user_job_by_id.return_value = mock_completed_job

        response = await use_case.execute(valid_request)

        assert isinstance(response, GetJobStatusResponse)
        assert response.success is True
        assert response.status == "completed"
        assert response.download_available is True

    @pytest.mark.asyncio
    async def test_execute_with_nonexistent_job_should_raise_video_job_not_found_exception(
            self, use_case, valid_request, mock_job_repository
    ):
        mock_job_repository.find_user_job_by_id.return_value = None
        mock_job_repository.find_by_id.return_value = None

        with pytest.raises(VideoJobNotFoundException):
            await use_case.execute(valid_request)

    @pytest.mark.asyncio
    async def test_execute_with_processing_job_should_calculate_progress(
            self, use_case, valid_request, mock_job_repository, mock_processing_job
    ):
        mock_job_repository.find_user_job_by_id.return_value = mock_processing_job

        response = await use_case.execute(valid_request)

        assert response.status == "processing"
        assert response.progress_percentage is not None
        assert response.download_available is False

    @pytest.mark.asyncio
    async def test_execute_with_pending_job_should_return_zero_progress(
            self, use_case, valid_request, mock_job_repository
    ):
        pending_job = Mock()
        pending_job.id = "job-123"
        pending_job.user_id = "test-user-123"
        pending_job.status = JobStatus.PENDING
        pending_job.zip_file_path = None
        pending_job.is_completed = Mock(return_value=False)
        pending_job.is_pending = Mock(return_value=True)
        pending_job.is_processing = Mock(return_value=False)
        pending_job.is_failed = Mock(return_value=False)
        pending_job.is_cancelled = Mock(return_value=False)

        mock_job_repository.find_user_job_by_id.return_value = pending_job

        response = await use_case.execute(valid_request)

        assert response.status == "pending"
        assert response.progress_percentage == 0.0
        assert response.download_available is False

    @pytest.mark.asyncio
    async def test_execute_with_failed_job_should_return_none_progress(
            self, use_case, valid_request, mock_job_repository
    ):
        failed_job = Mock()
        failed_job.id = "job-123"
        failed_job.user_id = "test-user-123"
        failed_job.status = JobStatus.FAILED
        failed_job.zip_file_path = None
        failed_job.is_completed = Mock(return_value=False)
        failed_job.is_pending = Mock(return_value=False)
        failed_job.is_processing = Mock(return_value=False)
        failed_job.is_failed = Mock(return_value=True)
        failed_job.is_cancelled = Mock(return_value=False)

        mock_job_repository.find_user_job_by_id.return_value = failed_job

        response = await use_case.execute(valid_request)

        assert response.status == "failed"
        assert response.progress_percentage is None
        assert response.download_available is False

    @pytest.mark.asyncio
    async def test_execute_should_call_repository_with_correct_parameters(
            self, use_case, valid_request, mock_job_repository, mock_completed_job
    ):
        mock_job_repository.find_user_job_by_id.return_value = mock_completed_job

        await use_case.execute(valid_request)

        mock_job_repository.find_user_job_by_id.assert_called_once_with("job-123", "test-user-123")

    @pytest.mark.asyncio
    async def test_execute_should_calculate_estimated_completion_for_processing_job(
            self, use_case, valid_request, mock_job_repository, mock_processing_job
    ):
        mock_job_repository.find_user_job_by_id.return_value = mock_processing_job

        response = await use_case.execute(valid_request)

        assert response.estimated_completion is not None

    @pytest.mark.asyncio
    async def test_execute_should_not_calculate_completion_for_non_processing_job(
            self, use_case, valid_request, mock_job_repository, mock_completed_job
    ):
        mock_job_repository.find_user_job_by_id.return_value = mock_completed_job

        response = await use_case.execute(valid_request)

        assert response.estimated_completion is None

    @pytest.mark.asyncio
    async def test_execute_should_include_comprehensive_job_data(
            self, use_case, valid_request, mock_job_repository, mock_completed_job
    ):
        mock_completed_job.original_filename = "test_video.mp4"
        mock_completed_job.frame_count = 100
        mock_completed_job.created_at = datetime.utcnow()
        mock_completed_job.updated_at = datetime.utcnow()
        mock_completed_job.metadata = {"test": "data"}

        mock_job_repository.find_user_job_by_id.return_value = mock_completed_job

        response = await use_case.execute(valid_request)

        job_data = response.job_data
        assert "id" in job_data
        assert "original_filename" in job_data
        assert "frame_count" in job_data
        assert "created_at" in job_data
        assert "metadata" in job_data

    @pytest.mark.asyncio
    async def test_calculate_progress_percentage_should_handle_missing_start_time(
            self, use_case, valid_request, mock_job_repository
    ):
        processing_job = Mock()
        processing_job.id = "job-123"
        processing_job.user_id = "test-user-123"
        processing_job.status = JobStatus.PROCESSING
        processing_job.processing_started_at = None
        processing_job.duration = 60.0
        processing_job.zip_file_path = None
        processing_job.is_completed = Mock(return_value=False)
        processing_job.is_pending = Mock(return_value=False)
        processing_job.is_processing = Mock(return_value=True)
        processing_job.is_failed = Mock(return_value=False)
        processing_job.is_cancelled = Mock(return_value=False)

        mock_job_repository.find_user_job_by_id.return_value = processing_job

        response = await use_case.execute(valid_request)

        assert response.progress_percentage == 50.0  # Default value when no start time

    @pytest.mark.asyncio
    async def test_estimate_completion_time_should_handle_missing_duration(
            self, use_case, valid_request, mock_job_repository
    ):
        processing_job = Mock()
        processing_job.id = "job-123"
        processing_job.user_id = "test-user-123"
        processing_job.status = JobStatus.PROCESSING
        processing_job.processing_started_at = datetime.utcnow()
        processing_job.duration = None
        processing_job.zip_file_path = None
        processing_job.is_completed = Mock(return_value=False)
        processing_job.is_pending = Mock(return_value=False)
        processing_job.is_processing = Mock(return_value=True)
        processing_job.is_failed = Mock(return_value=False)
        processing_job.is_cancelled = Mock(return_value=False)

        mock_job_repository.find_user_job_by_id.return_value = processing_job

        response = await use_case.execute(valid_request)

        assert response.estimated_completion is None