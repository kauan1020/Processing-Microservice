import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from use_cases.video_processing.download_result_use_case import (
    DownloadProcessingResultUseCase,
    DownloadResultRequest,
    DownloadResultResponse
)
from domain.entities.video_job import VideoJob, JobStatus, VideoFormat
from domain.exceptions import (
    ProcessingException,
    InvalidVideoFormatException,
    VideoJobNotFoundException,
    AuthorizationException,
    InvalidJobStatusException,
    StorageException
)

class TestDownloadProcessingResultUseCase:

    @pytest.fixture
    def mock_job_repository(self):
        repository = Mock()
        repository.find_user_job_by_id = AsyncMock()
        repository.find_by_id = AsyncMock()
        repository.update = AsyncMock()
        return repository

    @pytest.fixture
    def mock_file_storage(self):
        storage = Mock()
        storage.get_file_size = AsyncMock(return_value=1024)
        return storage

    @pytest.fixture
    def use_case(self, mock_job_repository, mock_file_storage):
        return DownloadProcessingResultUseCase(
            job_repository=mock_job_repository,
            file_storage=mock_file_storage
        )

    @pytest.fixture
    def valid_request(self):
        return DownloadResultRequest(
            job_id="job-123",
            user_id="test-user-123"
        )

    @pytest.fixture
    def completed_job_with_zip(self, temp_zip_file):
        job = Mock()
        job.id = "job-123"
        job.user_id = "test-user-123"
        job.status = JobStatus.COMPLETED
        job.zip_file_path = temp_zip_file
        job.original_filename = "test_video.mp4"
        job.processing_completed_at = datetime.utcnow()
        return job

    @pytest.mark.asyncio
    async def test_execute_with_nonexistent_job_should_raise_video_job_not_found_exception(
            self, use_case, valid_request, mock_job_repository
    ):
        mock_job_repository.find_user_job_by_id.return_value = None
        mock_job_repository.find_by_id.return_value = None

        with pytest.raises(VideoJobNotFoundException):
            await use_case.execute(valid_request)

    @pytest.mark.asyncio
    async def test_execute_with_processing_job_should_raise_invalid_job_status_exception(
            self, use_case, valid_request, mock_job_repository
    ):
        processing_job = Mock()
        processing_job.status = JobStatus.PROCESSING
        processing_job.id = "job-123"
        mock_job_repository.find_user_job_by_id.return_value = processing_job

        with pytest.raises(InvalidJobStatusException):
            await use_case.execute(valid_request)

