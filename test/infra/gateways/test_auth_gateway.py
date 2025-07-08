import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import json

from infra.gateways.kafka_gateway import KafkaGateway
from infra.gateways.auth_gateway import AuthGateway, AuthGatewayException
from infra.gateways.user_service_gateway import UserServiceGateway, UserServiceException
from infra.gateways.notification_gateway import NotificationGateway
from domain.entities.video_job import VideoJob, JobStatus, VideoFormat

class TestAuthGateway:

    @pytest.fixture
    def gateway(self):
        return AuthGateway(
            auth_service_url="http://localhost:8001",
            timeout=10,
            retry_attempts=2,
            cache_ttl_seconds=300
        )

    @pytest.mark.asyncio
    async def test_validate_token_with_valid_response_should_return_token_data(self, gateway):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {
                "valid": True,
                "user_id": "user-123",
                "token_type": "access",
                "expires_at": "2023-12-31T23:59:59"
            }
        }

        with patch.object(gateway, '_make_request', return_value=mock_response):
            result = await gateway.validate_token("valid_token")

            assert result["valid"] is True
            assert result["user_id"] == "user-123"
            assert result["validation_method"] == "auth_service"

    @pytest.mark.asyncio
    async def test_validate_token_with_invalid_token_should_return_invalid_status(self, gateway):
        mock_response = Mock()
        mock_response.status_code = 401

        with patch.object(gateway, '_make_request', return_value=mock_response):
            result = await gateway.validate_token("invalid_token")

            assert result["valid"] is False
            assert result["error"] == "Token is invalid or expired"

    @pytest.mark.asyncio
    async def test_validate_token_with_network_error_should_raise_auth_gateway_exception(self, gateway):
        import httpx

        with patch.object(gateway, '_make_request', side_effect=httpx.RequestError("Network error")):
            with pytest.raises(AuthGatewayException, match="Network error"):
                await gateway.validate_token("token")

    @pytest.mark.asyncio
    async def test_validate_token_should_cache_valid_results(self, gateway):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {"valid": True, "user_id": "user-123"}
        }

        with patch.object(gateway, '_make_request', return_value=mock_response) as mock_request:
            # First call
            result1 = await gateway.validate_token("token")
            # Second call should use cache
            result2 = await gateway.validate_token("token")

            assert result1["valid"] is True
            assert result2["valid"] is True
            mock_request.assert_called_once()  # Only one actual request

    @pytest.mark.asyncio
    async def test_get_user_info_with_existing_user_should_return_user_data(self, gateway):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user_id": "user-123",
            "email": "user@example.com",
            "username": "testuser"
        }

        with patch.object(gateway, '_make_request', return_value=mock_response):
            result = await gateway.get_user_info("user-123")

            assert result["user_id"] == "user-123"
            assert result["email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_get_user_info_with_nonexistent_user_should_return_none(self, gateway):
        mock_response = Mock()
        mock_response.status_code = 404

        with patch.object(gateway, '_make_request', return_value=mock_response):
            result = await gateway.get_user_info("nonexistent-user")

            assert result is None

    @pytest.mark.asyncio
    async def test_refresh_token_with_valid_refresh_token_should_return_new_tokens(self, gateway):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600
        }

        with patch.object(gateway, '_make_request', return_value=mock_response):
            result = await gateway.refresh_token("valid_refresh_token")

            assert result["access_token"] == "new_access_token"
            assert result["refresh_token"] == "new_refresh_token"

    @pytest.mark.asyncio
    async def test_check_user_permissions_with_allowed_action_should_return_true(self, gateway):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"allowed": True}

        with patch.object(gateway, '_make_request', return_value=mock_response):
            result = await gateway.check_user_permissions("user-123", "video", "process")

            assert result is True

    @pytest.mark.asyncio
    async def test_check_user_permissions_with_denied_action_should_return_false(self, gateway):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"allowed": False}

        with patch.object(gateway, '_make_request', return_value=mock_response):
            result = await gateway.check_user_permissions("user-123", "admin", "delete")

            assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_token_should_clear_cache_and_return_success(self, gateway):
        # Add token to cache first
        cache_key = f"token:{hash('test_token')}"
        gateway.token_cache[cache_key] = ({"valid": True}, datetime.utcnow())

        mock_response = Mock()
        mock_response.status_code = 200

        with patch.object(gateway, '_make_request', return_value=mock_response):
            result = await gateway.invalidate_token("test_token")

            assert result is True
            assert cache_key not in gateway.token_cache

    @pytest.mark.asyncio
    async def test_health_check_should_return_service_status(self, gateway):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "version": "1.0.0"
        }

        with patch.object(gateway, '_make_request', return_value=mock_response):
            result = await gateway.health_check()

            assert result["healthy"] is True
            assert result["version"] == "1.0.0"
            assert "response_time" in result

    @pytest.mark.asyncio
    async def test_clear_cache_should_remove_all_cached_data(self, gateway):
        gateway.token_cache["test"] = ({"valid": True}, datetime.utcnow())
        gateway.user_cache["test"] = ({"user_id": "123"}, datetime.utcnow())

        await gateway.clear_cache()

        assert len(gateway.token_cache) == 0
        assert len(gateway.user_cache) == 0

    @pytest.mark.asyncio
    async def test_close_should_cleanup_http_client(self, gateway):
        with patch.object(gateway.client, 'aclose') as mock_close:
            await gateway.close()
            mock_close.assert_called_once()
