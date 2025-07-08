import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import json

from infra.gateways.kafka_gateway import KafkaGateway

from domain.entities.video_job import VideoJob, JobStatus, VideoFormat


class TestKafkaGateway:

    @pytest.fixture
    def mock_kafka_service(self):
        service = Mock()
        service.initialize = AsyncMock()
        service.ensure_topics_exist = AsyncMock()
        service.publish_job_submitted = AsyncMock(return_value=True)
        service.publish_job_completed = AsyncMock(return_value=True)
        service.publish_job_failed = AsyncMock(return_value=True)
        service.publish_message = AsyncMock(return_value=True)
        service.publish_notification = AsyncMock(return_value=True)
        service.publish_system_alert = AsyncMock(return_value=True)
        service.create_consumer = AsyncMock()
        service.consume_messages = AsyncMock()
        service.get_consumer_lag = AsyncMock(return_value={"total_lag": 0})
        service.close = AsyncMock()
        service.topics = {
            "video_jobs": "video-processing-jobs",
            "notifications": "notifications",
            "system_alerts": "system-alerts"
        }
        service.consumers = {}
        service.producer = Mock()
        return service

    @pytest.fixture
    def gateway(self, mock_kafka_service):
        gateway = KafkaGateway("localhost:9092")
        gateway.kafka_service = mock_kafka_service
        return gateway

    @pytest.mark.asyncio
    async def test_health_check_with_unhealthy_service_should_return_unhealthy_status(
            self, gateway, mock_kafka_service
    ):
        gateway.is_initialized = True
        mock_kafka_service.producer = None

        result = await gateway.health_check()

        assert result["healthy"] is False
        assert result["status"] == "degraded"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_publish_job_submitted_with_video_job_entity_should_extract_data_correctly(
            self, gateway, mock_kafka_service
    ):
        video_job = Mock()
        video_job.id = "job-123"
        video_job.user_id = "user-456"
        video_job.original_filename = "test.mp4"
        video_job.file_size = 1024 * 1024
        video_job.video_format = VideoFormat.MP4
        video_job.extraction_fps = 1.0
        video_job.status = JobStatus.PENDING
        video_job.created_at = datetime.utcnow()
        video_job.metadata = {}

        await gateway.publish_job_submitted(video_job)

        mock_kafka_service.publish_job_submitted.assert_called_once()
        call_args = mock_kafka_service.publish_job_submitted.call_args[0][0]
        assert call_args["job_id"] == "job-123"
        assert call_args["user_id"] == "user-456"
        assert call_args["video_format"] == "mp4"

    @pytest.mark.asyncio
    async def test_publish_job_submitted_with_dict_should_pass_through_directly(
            self, gateway, mock_kafka_service
    ):
        job_data = {
            "job_id": "job-123",
            "user_id": "user-456",
            "original_filename": "test.mp4"
        }

        await gateway.publish_job_submitted(job_data)

        mock_kafka_service.publish_job_submitted.assert_called_once_with(job_data)

    @pytest.mark.asyncio
    async def test_publish_job_started_should_format_message_with_worker_info(
            self, gateway, mock_kafka_service
    ):
        video_job = Mock()
        video_job.id = "job-123"
        video_job.user_id = "user-456"
        video_job.original_filename = "test.mp4"
        video_job.file_size = 1024 * 1024
        video_job.video_format = VideoFormat.MP4
        video_job.extraction_fps = 1.0

        await gateway.publish_job_started(video_job, "worker-789")

        mock_kafka_service.publish_message.assert_called_once()
        call_args = mock_kafka_service.publish_message.call_args
        message = call_args[1]["message"]
        assert message["event_type"] == "job_started"
        assert message["worker_id"] == "worker-789"

    @pytest.mark.asyncio
    async def test_publish_job_failed_should_include_error_information(
            self, gateway, mock_kafka_service
    ):
        video_job = Mock()
        video_job.id = "job-123"
        video_job.user_id = "user-456"
        video_job.original_filename = "test.mp4"
        video_job.status = JobStatus.FAILED
        video_job.error_message = "Processing failed"
        video_job.updated_at = datetime.utcnow()

        error_message = "Video format not supported"
        retry_count = 2

        await gateway.publish_job_failed(video_job, error_message, retry_count)

        mock_kafka_service.publish_job_failed.assert_called_once()
        call_args = mock_kafka_service.publish_job_failed.call_args
        job_data = call_args[0][0]
        assert job_data["retry_count"] == retry_count

    @pytest.mark.asyncio
    async def test_publish_notification_request_should_enhance_with_metadata(
            self, gateway, mock_kafka_service
    ):
        notification_type = "job_completed"
        user_email = "user@example.com"
        template_data = {"job_id": "job-123", "filename": "test.mp4"}
        priority = "high"

        await gateway.publish_notification_request(
            notification_type, user_email, template_data, priority
        )

        mock_kafka_service.publish_notification.assert_called_once()
        call_args = mock_kafka_service.publish_notification.call_args[0][0]
        assert call_args["notification_type"] == notification_type
        assert call_args["priority"] == priority
        assert "timestamp" in call_args
        assert call_args["service"] == "video-processing"

    @pytest.mark.asyncio
    async def test_consume_processing_jobs_should_setup_consumer_correctly(
            self, gateway, mock_kafka_service
    ):
        mock_consumer = Mock()
        mock_kafka_service.create_consumer.return_value = mock_consumer

        handler_func = AsyncMock()

        await gateway.consume_processing_jobs(handler_func, "test-group", 5)

        mock_kafka_service.create_consumer.assert_called_once_with(
            topics=["video-processing-jobs"], consumer_group="test-group"
        )
        mock_kafka_service.consume_messages.assert_called_once_with(
            consumer=mock_consumer, message_handler=handler_func, max_messages=5
        )

    @pytest.mark.asyncio
    async def test_consume_notifications_should_setup_consumer_for_notifications(
            self, gateway, mock_kafka_service
    ):
        mock_consumer = Mock()
        mock_kafka_service.create_consumer.return_value = mock_consumer

        handler_func = AsyncMock()

        await gateway.consume_notifications(handler_func, "notification-group", 10)

        mock_kafka_service.create_consumer.assert_called_once_with(
            topics=["notifications"], consumer_group="notification-group"
        )
        mock_kafka_service.consume_messages.assert_called_once_with(
            consumer=mock_consumer, message_handler=handler_func, max_messages=10
        )

    @pytest.mark.asyncio
    async def test_stop_consuming_should_cleanup_and_set_shutdown_flag(
            self, gateway, mock_kafka_service
    ):
        gateway.is_initialized = True

        await gateway.stop_consuming()

        assert gateway.shutdown_requested is True
        mock_kafka_service.close.assert_called_once()
        assert gateway.is_initialized is False

    @pytest.mark.asyncio
    async def test_get_consumer_lag_should_enhance_base_metrics(
            self, gateway, mock_kafka_service
    ):
        gateway.is_initialized = True
        mock_kafka_service.get_consumer_lag.return_value = {
            "consumer_group": "test-group",
            "topic": "test-topic",
            "total_lag": 5
        }

        result = await gateway.get_consumer_lag("test-group", "test-topic")

        assert result["service_status"] == "active"
        assert result["initialization_status"] == "initialized"
        assert "check_timestamp" in result

    @pytest.mark.asyncio
    async def test_publish_system_alert_should_enhance_metadata(
            self, gateway, mock_kafka_service
    ):
        alert_type = "error"
        message = "High CPU usage"
        metadata = {"cpu_usage": 95}

        await gateway.publish_system_alert(alert_type, message, metadata)

        mock_kafka_service.publish_system_alert.assert_called_once()
        call_args = mock_kafka_service.publish_system_alert.call_args
        enhanced_metadata = call_args[1]["metadata"]
        assert enhanced_metadata["source"] == "kafka_gateway"
        assert enhanced_metadata["service"] == "video-processing"
        assert "timestamp" in enhanced_metadata

    @pytest.mark.asyncio
    async def test_methods_with_shutdown_requested_should_return_early(self, gateway):
        gateway.shutdown_requested = True

        result1 = await gateway.publish_job_submitted({})
        result2 = await gateway.publish_notification_request("test", "email", {})
        result3 = await gateway.get_consumer_lag("group", "topic")

        assert result1 is False
        assert result2 is False
        assert "Service is shutting down" in result3["error"]
