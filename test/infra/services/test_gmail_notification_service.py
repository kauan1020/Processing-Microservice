import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import tempfile
import os
import subprocess
import json
from datetime import datetime

from infra.services.video_processor_service import VideoProcessorService
from infra.services.file_storage_service import FileStorageService
from infra.services.kafka_service import KafkaService
from infra.services.gmail_notification_service import GmailNotificationService
from domain.value_objects import VideoFile, FrameExtractionConfig
from domain.exceptions import FFmpegException, VideoCorruptedException, StorageException


class TestGmailNotificationService:

    @pytest.fixture
    def service(self):
        return GmailNotificationService(
            gmail_email="test@gmail.com",
            gmail_app_password="test_password"
        )

    @pytest.mark.asyncio
    async def test_send_email_should_create_proper_mime_message(self, service):
        to_email = "test@example.com"
        subject = "Test Subject"
        html_content = "<h1>Test HTML Body</h1>"
        text_content = "Test Text Body"

        with patch.object(service, '_send_smtp_email') as mock_smtp:
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_executor = AsyncMock()
                mock_loop.return_value.run_in_executor = mock_executor

                result = await service._send_email(to_email, subject, html_content, text_content)

                assert result is True
                mock_executor.assert_called_once()

    def test_send_smtp_email_should_use_correct_smtp_settings(self, service):
        from email.mime.multipart import MIMEMultipart
        import ssl

        message = MIMEMultipart()
        context = ssl.create_default_context()

        with patch('smtplib.SMTP') as mock_smtp_class:
            mock_server = Mock()
            mock_smtp_class.return_value.__enter__.return_value = mock_server

            service._send_smtp_email(message, context)

            mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587)
            mock_server.starttls.assert_called_once_with(context=context)
            mock_server.login.assert_called_once_with(service.gmail_email, service.gmail_app_password)

    def test_create_completion_email_html_should_include_job_details(self, service):
        job_data = {
            "original_filename": "test_video.mp4",
            "frame_count": 100,
            "zip_size_mb": 5.2,
            "processing_duration_minutes": 2.5
        }
        download_url = "https://example.com/download/123"

        html_content = service._create_completion_email_html(job_data, download_url)

        assert "test_video.mp4" in html_content
        assert "100" in html_content
        assert download_url in html_content
        assert "Video Processing Complete" in html_content

    def test_create_completion_email_text_should_include_job_details(self, service):
        job_data = {
            "original_filename": "test_video.mp4",
            "frame_count": 100,
            "zip_size_mb": 5.2,
            "processing_duration_minutes": 2.5
        }
        download_url = "https://example.com/download/123"

        text_content = service._create_completion_email_text(job_data, download_url)

        assert "test_video.mp4" in text_content
        assert "100" in text_content
        assert download_url in text_content
        assert "Video Processing Complete" in text_content

    def test_create_failure_email_html_should_include_error_details(self, service):
        job_data = {
            "original_filename": "test_video.mp4",
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:05:00"
        }
        error_message = "Video format not supported"

        html_content = service._create_failure_email_html(job_data, error_message)

        assert "test_video.mp4" in html_content
        assert error_message in html_content
        assert "Video Processing Failed" in html_content
        assert "2023-01-01T12:00:00" in html_content

    def test_create_failure_email_text_should_include_error_details(self, service):
        job_data = {
            "original_filename": "test_video.mp4",
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:05:00"
        }
        error_message = "Video format not supported"

        text_content = service._create_failure_email_text(job_data, error_message)

        assert "test_video.mp4" in text_content
        assert error_message in text_content
        assert "Video Processing Failed" in text_content

    def test_create_alert_email_html_should_include_metadata(self, service):
        alert_type = "error"
        message = "System overload detected"
        metadata = {"cpu_usage": 95, "memory_usage": 90}

        html_content = service._create_alert_email_html(alert_type, message, metadata)

        assert alert_type.upper() in html_content
        assert message in html_content
        assert "cpu_usage" in html_content
        assert "95" in html_content
        assert "#f44336" in html_content  # Error color

    def test_create_alert_email_text_should_include_all_information(self, service):
        alert_type = "warning"
        message = "High memory usage detected"
        metadata = {"memory_usage": 85, "service": "video-processor"}

        text_content = service._create_alert_email_text(alert_type, message, metadata)

        assert alert_type.upper() in text_content
        assert message in text_content
        assert "memory_usage: 85" in text_content
        assert "service: video-processor" in text_content