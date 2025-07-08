import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import os
from domain.entities.video_job import VideoJob, VideoFormat, JobStatus
from datetime import datetime


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_database_session():
    """Mock database session for repository operations."""
    session = Mock()
    session.add = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = Mock(return_value=None)
    session.scalars = Mock()
    session.flush = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_database_session):
    """Mock session factory returning database session."""
    factory = AsyncMock()
    factory.return_value = mock_database_session
    return factory


@pytest.fixture
def temp_directory():
    """Create temporary directory for file operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def temp_video_file():
    """Create temporary video file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        temp_file.write(b"fake video content")
        temp_file_path = temp_file.name

    yield temp_file_path

    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)


@pytest.fixture
def temp_zip_file():
    """Create temporary ZIP file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
        temp_file.write(b"fake zip content")
        temp_file_path = temp_file.name

    yield temp_file_path

    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)


@pytest.fixture
def mock_video_job():
    """Mock VideoJob entity with realistic attributes."""

    job = Mock(spec=VideoJob)
    job.id = "test-job-123"
    job.user_id = "test-user-123"
    job.original_filename = "test_video.mp4"
    job.file_path = "/test/path/video.mp4"
    job.file_size = 1024 * 1024
    job.video_format = VideoFormat.MP4
    job.duration = 60.0
    job.frame_rate = 30.0
    job.extraction_fps = 1.0
    job.status = JobStatus.PENDING
    job.frame_count = None
    job.zip_file_path = None
    job.zip_file_size = None
    job.error_message = None
    job.processing_started_at = None
    job.processing_completed_at = None
    job.created_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    job.metadata = {}

    job.get_file_size_mb = Mock(return_value=1.0)
    job.get_zip_size_mb = Mock(return_value=0.5)
    job.get_processing_duration = Mock(return_value=120.0)
    job.get_estimated_frames = Mock(return_value=60)
    job.is_pending = Mock(return_value=True)
    job.is_processing = Mock(return_value=False)
    job.is_completed = Mock(return_value=False)
    job.is_failed = Mock(return_value=False)

    return job


@pytest.fixture
def mock_completed_video_job(mock_video_job):
    """Mock video job in completed state."""
    job = mock_video_job
    job.status = JobStatus.COMPLETED
    job.frame_count = 60
    job.zip_file_path = "/test/results/frames.zip"
    job.zip_file_size = 2048
    job.processing_completed_at = datetime.utcnow()
    job.is_pending = Mock(return_value=False)
    job.is_processing = Mock(return_value=False)
    job.is_completed = Mock(return_value=True)
    job.is_failed = Mock(return_value=False)
    return job


@pytest.fixture
def mock_failed_video_job(mock_video_job):
    """Mock video job in failed state."""
    job = mock_video_job
    job.status = JobStatus.FAILED
    job.error_message = "Processing failed"
    job.processing_completed_at = datetime.utcnow()
    job.is_pending = Mock(return_value=False)
    job.is_processing = Mock(return_value=False)
    job.is_completed = Mock(return_value=False)
    job.is_failed = Mock(return_value=True)
    return job


@pytest.fixture
def mock_video_file():
    """Mock VideoFile value object."""
    from domain.value_objects import VideoFile

    video_file = Mock(spec=VideoFile)
    video_file.file_path = "/test/path/video.mp4"
    video_file.original_name = "test_video.mp4"
    video_file.size_bytes = 1024 * 1024
    video_file.is_valid_video_format = Mock(return_value=True)
    video_file.get_extension = Mock(return_value=".mp4")
    video_file.get_size_mb = Mock(return_value=1.0)
    return video_file


@pytest.fixture
def mock_frame_extraction_config():
    """Mock FrameExtractionConfig value object."""
    from domain.value_objects import FrameExtractionConfig

    config = Mock(spec=FrameExtractionConfig)
    config.fps = 1.0
    config.output_format = "png"
    config.quality = 95
    config.start_time = 0.0
    config.end_time = None
    config.max_frames = None
    config.estimate_frame_count = Mock(return_value=60)
    return config


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    logger = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    return logger


@pytest.fixture
def mock_settings():
    """Mock application settings."""
    settings = Mock()
    settings.database.url = "postgresql://test:test@localhost/test"
    settings.database.echo = False
    settings.processing.ffmpeg_path = "/usr/bin/ffmpeg"
    settings.processing.ffprobe_path = "/usr/bin/ffprobe"
    settings.processing.max_concurrent_jobs = 4
    settings.processing.max_file_size_mb = 500
    settings.storage.base_path = "/tmp/test_storage"
    settings.kafka.bootstrap_servers = "localhost:9092"
    settings.kafka.security_protocol = "PLAINTEXT"
    settings.notification.gmail_email = "test@example.com"
    settings.notification.gmail_app_password = "test_password"
    settings.notification.from_name = "Test Service"
    settings.notification.get_admin_emails_list = Mock(return_value=[])
    settings.auth.service_url = "http://localhost:8001"
    settings.auth.timeout = 30
    settings.user_service.service_url = "http://localhost:8002"
    settings.user_service.timeout = 30
    settings.user_service.api_key = "test_api_key"
    return settings


@pytest.fixture
def mock_user_info():
    """Mock user information response."""
    return {
        "id": "test-user-123",
        "email": "test@example.com",
        "name": "Test User",
        "created_at": "2023-01-01T00:00:00Z"
    }


@pytest.fixture
def mock_example_user_info():
    """Mock user information with example email."""
    return {
        "id": "test-user-123",
        "email": "user_test-user-123@example.com",
        "name": "Test User"
    }


@pytest.fixture
def mock_file_processing_patches():
    """Common patches for file processing operations."""
    with patch('os.path.dirname', return_value="/tmp/frames"), \
            patch('os.listdir', return_value=["frame1.png", "frame2.png"]), \
            patch('os.path.join', side_effect=lambda *args: "/".join(args)), \
            patch('os.path.getsize', return_value=1024), \
            patch('os.makedirs'), \
            patch('shutil.rmtree'), \
            patch('shutil.move'), \
            patch('tempfile.NamedTemporaryFile') as mock_temp_file, \
            patch('zipfile.ZipFile') as mock_zip:
        mock_temp_file.return_value.__enter__.return_value.name = "/tmp/test.zip"
        mock_zip.return_value.__enter__.return_value.write = Mock()

        yield {
            'temp_file': mock_temp_file,
            'zip_file': mock_zip
        }


@pytest.fixture(autouse=True)
def mock_get_settings(mock_settings):
    """Automatically mock settings for all tests."""
    with patch('infra.settings.settings.get_settings', return_value=mock_settings):
        yield mock_settings


@pytest.fixture
def mock_successful_processing_environment(mock_file_processing_patches):
    """Setup successful processing environment with all necessary patches."""
    return mock_file_processing_patches