import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import json

from infra.gateways.kafka_gateway import KafkaGateway
from infra.gateways.auth_gateway import AuthGateway, AuthGatewayException
from infra.gateways.user_service_gateway import UserServiceGateway, UserServiceException
from infra.gateways.notification_gateway import NotificationGateway
from domain.entities.video_job import VideoJob, JobStatus, VideoFormat


class TestUserServiceGateway:

    @pytest.fixture
    def gateway(self):
        return UserServiceGateway(
            user_service_url="http://localhost:8002",
            timeout=10,
            retry_attempts=2,
            cache_ttl_seconds=300
        )

    @pytest.mark.asyncio
    async def test_verify_user_exists_with_existing_user_should_return_true(self, gateway):
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session

            result = await gateway.verify_user_exists("existing-user")

            assert result is True

    @pytest.mark.asyncio
    async def test_verify_user_exists_with_timeout_should_default_to_true(self, gateway):
        import asyncio

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session_class.side_effect = asyncio.TimeoutError()

            result = await gateway.verify_user_exists("user-123")

            assert result is True



    @pytest.mark.asyncio
    async def test_get_user_info_with_error_should_return_default_info(self, gateway):
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session_class.side_effect = Exception("Network error")

            result = await gateway.get_user_info("user-123")

            assert result["id"] == "user-123"
            assert result["email"] == "user_user-123@example.com"
            assert result["username"] == "user_user-123"

    @pytest.mark.asyncio
    async def test_get_user_preferences_should_return_user_specific_preferences(self, gateway):
        mock_user_info = {
            "id": "user-123",
            "preferences": {
                "notifications": {"email_enabled": True},
                "processing": {"default_quality": 90}
            }
        }

        with patch.object(gateway, 'get_user_info', return_value=mock_user_info):
            result = await gateway.get_user_preferences("user-123")

            assert result["notifications"]["email_enabled"] is True
            assert result["processing"]["default_quality"] == 90

    @pytest.mark.asyncio
    async def test_get_user_preferences_with_error_should_return_defaults(self, gateway):
        with patch.object(gateway, 'get_user_info', side_effect=Exception("Service error")):
            result = await gateway.get_user_preferences("user-123")

            assert "notifications" in result
            assert "processing" in result
            assert result["processing"]["default_quality"] == 95

    @pytest.mark.asyncio
    async def test_update_user_activity_should_return_true_in_development_mode(self, gateway):
        with patch.object(gateway, '_is_development', return_value=True):
            result = await gateway.update_user_activity("user-123", {"action": "test"})

            assert result is True

    @pytest.mark.asyncio
    async def test_update_user_activity_should_call_service_in_production(self, gateway):
        with patch.object(gateway, '_is_development', return_value=False):
            with patch('aiohttp.ClientSession') as mock_session_class:
                mock_session = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_session.post.return_value.__aenter__.return_value = mock_response
                mock_session_class.return_value.__aenter__.return_value = mock_session

                result = await gateway.update_user_activity("user-123", {"action": "test"})

                assert result is True


    def test_is_cache_valid_with_valid_cache_should_return_true(self, gateway):
        cache_key = "test_key"
        gateway._cache[cache_key] = {
            'data': {'test': 'data'},
            'timestamp': datetime.utcnow()
        }

        result = gateway._is_cache_valid(cache_key)

        assert result is True

    def test_is_cache_valid_with_expired_cache_should_return_false(self, gateway):
        cache_key = "test_key"
        gateway._cache[cache_key] = {
            'data': {'test': 'data'},
            'timestamp': datetime.utcnow() - timedelta(seconds=400)  # Expired
        }

        result = gateway._is_cache_valid(cache_key)

        assert result is False

    def test_get_from_cache_with_valid_cache_should_return_data(self, gateway):
        cache_key = "test_key"
        test_data = {'test': 'data'}
        gateway._cache[cache_key] = {
            'data': test_data,
            'timestamp': datetime.utcnow()
        }

        result = gateway._get_from_cache(cache_key)

        assert result == test_data

    def test_set_cache_should_store_data_with_timestamp(self, gateway):
        cache_key = "test_key"
        test_data = {'test': 'data'}

        gateway._set_cache(cache_key, test_data)

        assert cache_key in gateway._cache
        assert gateway._cache[cache_key]['data'] == test_data
        assert isinstance(gateway._cache[cache_key]['timestamp'], datetime)

    def test_is_development_should_detect_development_environment(self, gateway):
        with patch('os.getenv', return_value="development"):
            result = gateway._is_development()
            assert result is True

        with patch('os.getenv', return_value="production"):
            result = gateway._is_development()
            assert result is False

    def test_get_default_user_info_should_return_fallback_data(self, gateway):
        result = gateway._get_default_user_info("test-user-123")

        assert result["id"] == "test-user-123"
        assert result["email"] == "user_test-user-123@example.com"
        assert result["status"] == "active"

    def test_get_default_preferences_should_return_standard_defaults(self, gateway):
        result = gateway._get_default_preferences()

        assert "notifications" in result
        assert "processing" in result
        assert result["notifications"]["email_enabled"] is True
        assert result["processing"]["default_quality"] == 95
