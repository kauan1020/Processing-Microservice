import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import uuid

from infra.repositories.video_job_repository import VideoJobRepository
from domain.entities.video_job import VideoJob, JobStatus, VideoFormat
from domain.exceptions import VideoJobNotFoundException


class TestVideoJobRepository:

    @pytest.fixture
    def mock_session_factory(self):
        """Create a properly configured async context manager mock for session factory."""
        session = Mock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.scalar = Mock()
        session.scalars = Mock()

        # Configure as async context manager
        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=session)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)

        factory = Mock()
        factory.return_value = async_context_manager

        return factory

    @pytest.fixture
    def repository(self, mock_session_factory):
        return VideoJobRepository(mock_session_factory)

    @pytest.fixture
    def sample_video_job(self):
        return VideoJob(
            id="test-job-123",
            user_id="test-user-123",
            original_filename="test_video.mp4",
            file_path="/test/path/video.mp4",
            file_size=1024 * 1024,
            video_format=VideoFormat.MP4,
            duration=60.0,
            frame_rate=30.0,
            extraction_fps=1.0,
            status=JobStatus.PENDING,
            frame_count=None,
            zip_file_path=None,
            zip_file_size=None,
            error_message=None,
            processing_started_at=None,
            processing_completed_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )

    @pytest.fixture
    def mock_video_job_model(self):
        model = Mock()
        model.id = "test-job-123"
        model.user_id = "test-user-123"
        model.original_filename = "test_video.mp4"
        model.file_path = "/test/path/video.mp4"
        model.file_size = 1024 * 1024
        model.video_format = "mp4"
        model.duration = 60.0
        model.frame_rate = 30.0
        model.extraction_fps = 1.0
        model.status = "pending"
        model.frame_count = None
        model.zip_file_path = None
        model.zip_file_size = None
        model.error_message = None
        model.processing_started_at = None
        model.processing_completed_at = None
        model.created_at = datetime.utcnow()
        model.updated_at = datetime.utcnow()
        model.job_metadata = {}
        return model

    def get_session_from_factory(self, mock_session_factory):
        """Helper to get the mock session from the factory."""
        return mock_session_factory.return_value.__aenter__.return_value

    @pytest.mark.asyncio
    async def test_create_with_valid_job_should_persist_successfully(
            self, repository, sample_video_job, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_model = Mock()
        mock_model.id = sample_video_job.id

        with patch('infra.repositories.video_job_repository.VideoJobModel', return_value=mock_model), \
                patch.object(repository, '_model_to_entity', return_value=sample_video_job):
            result = await repository.create(sample_video_job)

            assert result == sample_video_job
            session.add.assert_called_once()
            session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_id_with_existing_job_should_return_job(
            self, repository, mock_session_factory, mock_video_job_model, sample_video_job
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_video_job_model
        session.execute.return_value = mock_result

        with patch.object(repository, '_model_to_entity', return_value=sample_video_job):
            result = await repository.find_by_id("test-job-123")

            assert result == sample_video_job
            session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_id_with_nonexistent_job_should_return_none(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        result = await repository.find_by_id("nonexistent-job")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_user_id_should_return_user_jobs_with_pagination(
            self, repository, mock_session_factory, mock_video_job_model, sample_video_job
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_video_job_model, mock_video_job_model]
        session.execute.return_value = mock_result

        with patch.object(repository, '_model_to_entity', return_value=sample_video_job):
            result = await repository.find_by_user_id("test-user-123", skip=0, limit=10)

            assert len(result) == 2
            assert all(job == sample_video_job for job in result)

    @pytest.mark.asyncio
    async def test_find_by_status_should_filter_jobs_by_status(
            self, repository, mock_session_factory, mock_video_job_model, sample_video_job
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_video_job_model]
        session.execute.return_value = mock_result

        with patch.object(repository, '_model_to_entity', return_value=sample_video_job):
            result = await repository.find_by_status(JobStatus.PENDING)

            assert len(result) == 1
            assert result[0] == sample_video_job

    @pytest.mark.asyncio
    async def test_find_by_user_and_status_should_filter_by_both_criteria(
            self, repository, mock_session_factory, mock_video_job_model, sample_video_job
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_video_job_model]
        session.execute.return_value = mock_result

        with patch.object(repository, '_model_to_entity', return_value=sample_video_job):
            result = await repository.find_by_user_and_status(
                "test-user-123", JobStatus.PENDING
            )

            assert len(result) == 1
            assert result[0] == sample_video_job

    @pytest.mark.asyncio
    async def test_count_by_user_and_status_should_return_correct_count(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalar.return_value = 5
        session.execute.return_value = mock_result

        result = await repository.count_by_user_and_status("test-user-123", JobStatus.PENDING)

        assert result == 5

    @pytest.mark.asyncio
    async def test_find_user_job_by_id_with_authorized_access_should_return_job(
            self, repository, mock_session_factory, mock_video_job_model, sample_video_job
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_video_job_model
        session.execute.return_value = mock_result

        with patch.object(repository, '_model_to_entity', return_value=sample_video_job):
            result = await repository.find_user_job_by_id("test-job-123", "test-user-123")

            assert result == sample_video_job

    @pytest.mark.asyncio
    async def test_find_user_job_by_id_with_unauthorized_access_should_return_none(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        result = await repository.find_user_job_by_id("test-job-123", "different-user-456")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_with_existing_job_should_update_successfully(
            self, repository, sample_video_job, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.rowcount = 1
        session.execute.return_value = mock_result

        sample_video_job.status = JobStatus.COMPLETED
        sample_video_job.frame_count = 100

        result = await repository.update(sample_video_job)

        assert result == sample_video_job
        assert sample_video_job.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_with_nonexistent_job_should_raise_video_job_not_found_exception(
            self, repository, sample_video_job, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.rowcount = 0
        session.execute.return_value = mock_result

        with pytest.raises(VideoJobNotFoundException):
            await repository.update(sample_video_job)

    @pytest.mark.asyncio
    async def test_delete_with_existing_job_should_return_true(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.rowcount = 1
        session.execute.return_value = mock_result

        result = await repository.delete("test-job-123")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_with_nonexistent_job_should_return_false(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.rowcount = 0
        session.execute.return_value = mock_result

        result = await repository.delete("nonexistent-job")

        assert result is False

    @pytest.mark.asyncio
    async def test_count_by_user_id_should_return_total_count(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalar.return_value = 10
        session.execute.return_value = mock_result

        result = await repository.count_by_user_id("test-user-123")

        assert result == 10

    @pytest.mark.asyncio
    async def test_count_by_status_should_return_status_count(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalar.return_value = 3
        session.execute.return_value = mock_result

        result = await repository.count_by_status(JobStatus.PROCESSING)

        assert result == 3

    @pytest.mark.asyncio
    async def test_find_pending_jobs_should_return_ordered_pending_jobs(
            self, repository, mock_session_factory, mock_video_job_model, sample_video_job
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_video_job_model, mock_video_job_model]
        session.execute.return_value = mock_result

        with patch.object(repository, '_model_to_entity', return_value=sample_video_job):
            result = await repository.find_pending_jobs(limit=10)

            assert len(result) == 2
            assert all(job == sample_video_job for job in result)

    @pytest.mark.asyncio
    async def test_find_stale_processing_jobs_should_return_stuck_jobs(
            self, repository, mock_session_factory, mock_video_job_model, sample_video_job
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_video_job_model]
        session.execute.return_value = mock_result

        with patch.object(repository, '_model_to_entity', return_value=sample_video_job):
            result = await repository.find_stale_processing_jobs(timeout_minutes=60)

            assert len(result) == 1
            assert result[0] == sample_video_job

    @pytest.mark.asyncio
    async def test_find_jobs_by_date_range_should_filter_by_dates(
            self, repository, mock_session_factory, mock_video_job_model, sample_video_job
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_video_job_model]
        session.execute.return_value = mock_result

        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        with patch.object(repository, '_model_to_entity', return_value=sample_video_job):
            result = await repository.find_jobs_by_date_range(start_date, end_date)

            assert len(result) == 1
            assert result[0] == sample_video_job

    @pytest.mark.asyncio
    async def test_find_jobs_by_date_range_with_user_filter_should_include_user_criteria(
            self, repository, mock_session_factory, mock_video_job_model, sample_video_job
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_video_job_model]
        session.execute.return_value = mock_result

        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        with patch.object(repository, '_model_to_entity', return_value=sample_video_job):
            result = await repository.find_jobs_by_date_range(
                start_date, end_date, user_id="test-user-123"
            )

            assert len(result) == 1
            assert result[0] == sample_video_job

    @pytest.mark.asyncio
    async def test_get_user_job_statistics_should_return_comprehensive_stats(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)

        mock_results = [
            Mock(scalar=Mock(return_value=10)),  # total_jobs
            Mock(scalar=Mock(return_value=7)),  # completed_jobs
            Mock(scalar=Mock(return_value=1)),  # failed_jobs
            Mock(scalar=Mock(return_value=2)),  # pending_jobs
            Mock(scalar=Mock(return_value=0)),  # processing_jobs
            Mock(scalar=Mock(return_value=350)),  # total_frames
            Mock(scalar=Mock(return_value=1800))  # total_processing_time
        ]

        session.execute.side_effect = mock_results

        result = await repository.get_user_job_statistics("test-user-123")

        assert result["total_jobs"] == 10
        assert result["completed_jobs"] == 7
        assert result["failed_jobs"] == 1
        assert result["pending_jobs"] == 2
        assert result["processing_jobs"] == 0
        assert result["total_frames_extracted"] == 350
        assert result["total_processing_time"] == 1800.0

    @pytest.mark.asyncio
    async def test_cleanup_old_jobs_should_remove_old_completed_jobs(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.rowcount = 5
        session.execute.return_value = mock_result

        result = await repository.cleanup_old_jobs(days_old=30)

        assert result == 5

    def test_model_to_entity_should_convert_correctly(self, repository, mock_video_job_model):
        result = repository._model_to_entity(mock_video_job_model)

        assert isinstance(result, VideoJob)
        assert result.id == mock_video_job_model.id
        assert result.user_id == mock_video_job_model.user_id
        assert result.original_filename == mock_video_job_model.original_filename
        assert result.status == JobStatus.PENDING
        assert result.video_format == VideoFormat.MP4

    def test_model_to_entity_with_none_values_should_handle_gracefully(self, repository):
        mock_model = Mock()
        mock_model.id = "test-job-123"
        mock_model.user_id = "test-user-123"
        mock_model.original_filename = "test.mp4"
        mock_model.file_path = "/test/path"
        mock_model.file_size = 1024
        mock_model.video_format = "mp4"
        mock_model.duration = None
        mock_model.frame_rate = None
        mock_model.extraction_fps = 1.0
        mock_model.status = "pending"
        mock_model.frame_count = None
        mock_model.zip_file_path = None
        mock_model.zip_file_size = None
        mock_model.error_message = None
        mock_model.processing_started_at = None
        mock_model.processing_completed_at = None
        mock_model.created_at = datetime.utcnow()
        mock_model.updated_at = datetime.utcnow()
        mock_model.job_metadata = None

        result = repository._model_to_entity(mock_model)

        assert isinstance(result, VideoJob)
        assert result.duration is None
        assert result.frame_rate is None
        assert result.metadata is None

    @pytest.mark.asyncio
    async def test_execute_with_session_should_handle_commit_and_rollback(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)

        async def operation(session):
            return "success"

        result = await repository._execute_with_session(operation)

        assert result == "success"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_session_should_rollback_on_exception(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        session.commit.side_effect = Exception("Database error")

        async def failing_operation(session):
            return "success"

        with pytest.raises(Exception, match="Database error"):
            await repository._execute_with_session(failing_operation)

        session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_read_only_should_not_commit_or_rollback(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)

        async def read_operation(session):
            return "read_result"

        result = await repository._execute_read_only(read_operation)

        assert result == "read_result"
        session.commit.assert_not_called()
        session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_count_methods_should_handle_none_results(
            self, repository, mock_session_factory
    ):
        session = self.get_session_from_factory(mock_session_factory)
        mock_result = Mock()
        mock_result.scalar.return_value = None
        session.execute.return_value = mock_result

        user_count = await repository.count_by_user_id("test-user-123")
        status_count = await repository.count_by_status(JobStatus.PENDING)
        user_status_count = await repository.count_by_user_and_status("test-user-123", JobStatus.PENDING)

        assert user_count == 0
        assert status_count == 0
        assert user_status_count == 0