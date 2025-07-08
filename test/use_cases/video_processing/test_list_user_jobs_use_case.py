import pytest
from unittest.mock import Mock, AsyncMock

from use_cases.video_processing.list_user_jobs_use_case import (
    ListUserJobsUseCase,
    ListUserJobsRequest,
    ListUserJobsResponse
)
from domain.entities.video_job import JobStatus


class TestListUserJobsUseCase:

    @pytest.fixture
    def mock_job_repository(self):
        repository = Mock()
        repository.find_by_user_id = AsyncMock(return_value=[])
        repository.find_by_user_and_status = AsyncMock(return_value=[])
        repository.count_by_user_id = AsyncMock(return_value=0)
        repository.count_by_user_and_status = AsyncMock(return_value=0)
        repository.get_user_job_statistics = AsyncMock(return_value={
            "total_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "pending_jobs": 0,
            "processing_jobs": 0,
            "total_frames_extracted": 0,
            "total_processing_time": 0.0
        })
        return repository

    @pytest.fixture
    def use_case(self, mock_job_repository):
        return ListUserJobsUseCase(job_repository=mock_job_repository)

    @pytest.fixture
    def valid_request(self):
        return ListUserJobsRequest(
            user_id="test-user-123",
            skip=0,
            limit=20
        )

    @pytest.fixture
    def mock_jobs(self):
        jobs = []
        for i in range(3):
            job = Mock()
            job.id = f"job-{i + 1}"
            job.original_filename = f"video{i + 1}.mp4"
            job.status = JobStatus.COMPLETED if i < 2 else JobStatus.PENDING
            job.frame_count = 60 if i < 2 else None
            job.zip_file_path = f"/test/result{i + 1}.zip" if i < 2 else None
            job.is_completed = Mock(return_value=i < 2)
            jobs.append(job)
        return jobs

    @pytest.mark.asyncio
    async def test_execute_without_status_filter_should_return_all_user_jobs(
            self, use_case, valid_request, mock_job_repository, mock_jobs
    ):
        mock_job_repository.find_by_user_id.return_value = mock_jobs
        mock_job_repository.count_by_user_id.return_value = 3

        response = await use_case.execute(valid_request)

        assert isinstance(response, ListUserJobsResponse)
        assert response.success is True
        assert response.total_count == 3
        assert len(response.jobs) == 3

    @pytest.mark.asyncio
    async def test_execute_with_status_filter_should_filter_jobs_correctly(
            self, use_case, mock_job_repository, mock_jobs
    ):
        filtered_request = ListUserJobsRequest(
            user_id="test-user-123",
            status_filter=JobStatus.COMPLETED,
            skip=0,
            limit=20
        )

        completed_jobs = [job for job in mock_jobs if job.status == JobStatus.COMPLETED]
        mock_job_repository.find_by_user_and_status.return_value = completed_jobs
        mock_job_repository.count_by_user_and_status.return_value = len(completed_jobs)

        response = await use_case.execute(filtered_request)

        assert response.total_count == 2
        mock_job_repository.find_by_user_and_status.assert_called_once_with(
            "test-user-123", JobStatus.COMPLETED, 0, 20
        )

    @pytest.mark.asyncio
    async def test_execute_should_include_user_statistics(
            self, use_case, valid_request, mock_job_repository
    ):
        expected_stats = {
            "total_jobs": 5,
            "completed_jobs": 3,
            "failed_jobs": 1,
            "pending_jobs": 1,
            "processing_jobs": 0,
            "total_frames_extracted": 300,
            "total_processing_time": 1800.0
        }
        mock_job_repository.get_user_job_statistics.return_value = expected_stats

        response = await use_case.execute(valid_request)

        assert response.statistics == expected_stats
        mock_job_repository.get_user_job_statistics.assert_called_once_with("test-user-123")

    @pytest.mark.asyncio
    async def test_execute_should_respect_pagination_parameters(
            self, use_case, mock_job_repository, mock_jobs
    ):
        paginated_request = ListUserJobsRequest(
            user_id="test-user-123",
            skip=10,
            limit=5
        )

        mock_job_repository.find_by_user_id.return_value = mock_jobs[:2]  # Simulating pagination
        mock_job_repository.count_by_user_id.return_value = 15

        response = await use_case.execute(paginated_request)

        mock_job_repository.find_by_user_id.assert_called_once_with("test-user-123", 10, 5)
        assert response.total_count == 15

    @pytest.mark.asyncio
    async def test_execute_should_create_proper_pagination_info(
            self, use_case, valid_request, mock_job_repository, mock_jobs
    ):
        mock_job_repository.find_by_user_id.return_value = mock_jobs
        mock_job_repository.count_by_user_id.return_value = 25

        response = await use_case.execute(valid_request)

        page_info = response.page_info
        assert page_info["skip"] == 0
        assert page_info["limit"] == 20
        assert page_info["has_next"] is True  # 25 total, showing first 20
        assert page_info["has_previous"] is False
        assert page_info["total_pages"] == 2
        assert page_info["current_page"] == 1

    @pytest.mark.asyncio
    async def test_execute_should_create_job_summaries_correctly(
            self, use_case, valid_request, mock_job_repository, mock_jobs
    ):
        # Setup mock data
        for i, job in enumerate(mock_jobs):
            job.get_file_size_mb = Mock(return_value=5.0 + i)
            job.video_format = Mock()
            job.video_format.value = "mp4"
            job.duration = 60.0 + i * 10
            job.get_estimated_frames = Mock(return_value=60 + i * 10)
            job.get_zip_size_mb = Mock(return_value=2.0 + i if job.is_completed() else None)
            job.get_processing_duration = Mock(return_value=120.0 + i * 30 if job.is_completed() else None)
            job.created_at = Mock()
            job.created_at.isoformat = Mock(return_value=f"2023-01-0{i + 1}T12:00:00")
            job.processing_completed_at = Mock()
            if job.is_completed():
                job.processing_completed_at.isoformat = Mock(return_value=f"2023-01-0{i + 1}T12:05:00")
            else:
                job.processing_completed_at = None

        mock_job_repository.find_by_user_id.return_value = mock_jobs
        mock_job_repository.count_by_user_id.return_value = 3

        response = await use_case.execute(valid_request)

        job_summaries = response.jobs
        assert len(job_summaries) == 3

        # Check first job (completed)
        first_job = job_summaries[0]
        assert first_job["id"] == "job-1"
        assert first_job["original_filename"] == "video1.mp4"
        assert first_job["file_size_mb"] == 5.0
        assert first_job["video_format"] == "mp4"
        assert first_job["status"] == "completed"
        assert first_job["download_available"] is True

        # Check third job (pending)
        third_job = job_summaries[2]
        assert third_job["id"] == "job-3"
        assert third_job["status"] == "pending"
        assert third_job["download_available"] is False

    @pytest.mark.asyncio
    async def test_execute_with_empty_results_should_handle_gracefully(
            self, use_case, valid_request, mock_job_repository
    ):
        mock_job_repository.find_by_user_id.return_value = []
        mock_job_repository.count_by_user_id.return_value = 0

        response = await use_case.execute(valid_request)

        assert response.success is True
        assert response.total_count == 0
        assert len(response.jobs) == 0
        assert response.page_info["has_next"] is False
        assert response.page_info["has_previous"] is False

    @pytest.mark.asyncio
    async def test_execute_should_handle_repository_exceptions_gracefully(
            self, use_case, valid_request, mock_job_repository
    ):
        mock_job_repository.find_by_user_id.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            await use_case.execute(valid_request)

    @pytest.mark.asyncio
    async def test_create_job_summary_should_handle_none_values(self, use_case):
        job = Mock()
        job.id = "job-123"
        job.original_filename = "test.mp4"
        job.get_file_size_mb = Mock(return_value=5.0)
        job.video_format = Mock()
        job.video_format.value = "mp4"
        job.duration = None
        job.status = Mock()
        job.status.value = "pending"
        job.frame_count = None
        job.get_estimated_frames = Mock(return_value=0)
        job.get_zip_size_mb = Mock(return_value=None)
        job.get_processing_duration = Mock(return_value=None)
        job.created_at = None
        job.processing_completed_at = None
        job.is_completed = Mock(return_value=False)
        job.zip_file_path = None

        summary = use_case._create_job_summary(job)

        assert summary["id"] == "job-123"
        assert summary["duration"] is None
        assert summary["frame_count"] is None
        assert summary["zip_size_mb"] is None
        assert summary["processing_duration"] is None
        assert summary["created_at"] is None
        assert summary["processing_completed_at"] is None
        assert summary["download_available"] is False

    @pytest.mark.asyncio
    async def test_create_pagination_info_should_calculate_correctly(self, use_case):
        request = ListUserJobsRequest(
            user_id="test-user-123",
            skip=40,
            limit=20
        )
        total_count = 100

        page_info = use_case._create_pagination_info(request, total_count)

        assert page_info["skip"] == 40
        assert page_info["limit"] == 20
        assert page_info["has_next"] is True  # 40 + 20 < 100
        assert page_info["has_previous"] is True  # 40 > 0
        assert page_info["total_pages"] == 5  # 100 / 20
        assert page_info["current_page"] == 3  # (40 / 20) + 1

    @pytest.mark.asyncio
    async def test_create_pagination_info_should_handle_edge_cases(self, use_case):
        # Test exact page boundary
        request = ListUserJobsRequest(
            user_id="test-user-123",
            skip=20,
            limit=20
        )
        total_count = 40

        page_info = use_case._create_pagination_info(request, total_count)

        assert page_info["has_next"] is False  # 20 + 20 = 40
        assert page_info["has_previous"] is True
        assert page_info["total_pages"] == 2
        assert page_info["current_page"] == 2

    @pytest.mark.asyncio
    async def test_execute_with_large_skip_value_should_handle_correctly(
            self, use_case, mock_job_repository
    ):
        request = ListUserJobsRequest(
            user_id="test-user-123",
            skip=1000,  # Large skip value
            limit=20
        )

        mock_job_repository.find_by_user_id.return_value = []
        mock_job_repository.count_by_user_id.return_value = 50  # Total less than skip

        response = await use_case.execute(request)

        assert response.total_count == 50
        assert len(response.jobs) == 0
        assert response.page_info["has_next"] is False
        assert response.page_info["has_previous"] is True