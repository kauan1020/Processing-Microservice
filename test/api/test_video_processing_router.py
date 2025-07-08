import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from fastapi.responses import FileResponse
import json
import base64
import os
import tempfile
from datetime import datetime, timedelta

from api.video_processing_router import (
    router,
    validate_user_token,
    get_current_user_id,
    get_video_processing_controller
)


@pytest.fixture
def mock_upload_file():
    content = b"fake video content"
    file = Mock(spec=UploadFile)
    file.filename = "test_video.mp4"
    file.size = len(content)
    file.content_type = "video/mp4"
    file.read = AsyncMock(return_value=content)
    file.file = Mock()
    return file


@pytest.fixture
def valid_jwt_token():
    payload = {
        "sub": "test-user-123",
        "user_id": "test-user-123",
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
        "username": "testuser",
        "email": "test@example.com"
    }

    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip('=')
    payload_encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    signature = "fake_signature"

    return f"{header}.{payload_encoded}.{signature}"


@pytest.fixture
def expired_jwt_token():
    payload = {
        "sub": "test-user-123",
        "user_id": "test-user-123",
        "exp": int((datetime.utcnow() - timedelta(hours=1)).timestamp()),
        "iat": int(datetime.utcnow().timestamp())
    }

    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip('=')
    payload_encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    signature = "fake_signature"

    return f"{header}.{payload_encoded}.{signature}"


@pytest.fixture
def mock_controller():
    controller = Mock()
    controller.submit_video_for_processing = AsyncMock(return_value={
        "success": True,
        "data": {"job": {"id": "test-job-id"}}
    })
    controller.get_job_status = AsyncMock(return_value={
        "success": True,
        "data": {"status": "completed", "job_data": {"metadata": {}}}
    })
    controller.list_user_jobs = AsyncMock(return_value={
        "success": True,
        "data": {"jobs": [], "pagination": {}}
    })
    controller.download_processing_result = AsyncMock(return_value={
        "success": True,
        "data": {"download": {"file_path": "/test/path"}}
    })
    controller.delete_video_job = AsyncMock(return_value={
        "success": True,
        "message": "Job deleted"
    })
    return controller


@pytest.fixture
def mock_user_service():
    service = Mock()
    service.verify_user_exists = AsyncMock(return_value=True)
    service.get_user_preferences = AsyncMock(return_value={
        "processing": {"default_quality": 95, "default_fps": 1.0}
    })
    service.update_user_activity = AsyncMock(return_value=True)
    service.health_check = AsyncMock(return_value={"healthy": True})
    return service


class TestTokenValidation:

    @pytest.mark.asyncio
    async def test_validate_user_token_with_valid_token_should_return_token_data(self, valid_jwt_token):
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_jwt_token
        )

        with patch('api.video_processing_router.get_auth_gateway') as mock_get_auth:
            mock_auth_gateway = Mock()
            mock_auth_gateway.validate_token = AsyncMock(
                side_effect=Exception("Service unavailable")
            )
            mock_get_auth.return_value = mock_auth_gateway

            result = await validate_user_token(credentials)

            assert result["valid"] is True
            assert result["user_id"] == "test-user-123"
            assert result["validation_method"] == "manual_decode"

    @pytest.mark.asyncio
    async def test_validate_user_token_with_expired_token_should_raise_http_exception(self, expired_jwt_token):
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=expired_jwt_token
        )

        with patch('api.video_processing_router.get_auth_gateway') as mock_get_auth:
            mock_auth_gateway = Mock()
            mock_auth_gateway.validate_token = AsyncMock(
                side_effect=Exception("Service unavailable")
            )
            mock_get_auth.return_value = mock_auth_gateway

            with pytest.raises(HTTPException) as exc_info:
                await validate_user_token(credentials)

            assert exc_info.value.status_code == 401
            assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_validate_user_token_with_invalid_format_should_raise_http_exception(self):
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid.token.format.extra"
        )

        with patch('api.video_processing_router.get_auth_gateway') as mock_get_auth:
            mock_auth_gateway = Mock()
            mock_auth_gateway.validate_token = AsyncMock(
                side_effect=Exception("Service unavailable")
            )
            mock_get_auth.return_value = mock_auth_gateway

            with pytest.raises(HTTPException) as exc_info:
                await validate_user_token(credentials)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_validate_user_token_with_auth_service_success_should_use_service_result(self, valid_jwt_token):
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_jwt_token
        )

        with patch('api.video_processing_router.get_auth_gateway') as mock_get_auth:
            mock_auth_gateway = Mock()
            mock_auth_gateway.validate_token = AsyncMock(return_value={
                "valid": True,
                "user_id": "test-user-123",
                "validation_method": "auth_service"
            })
            mock_get_auth.return_value = mock_auth_gateway

            result = await validate_user_token(credentials)

            assert result["valid"] is True
            assert result["user_id"] == "test-user-123"
            assert result["validation_method"] == "auth_service"

    @pytest.mark.asyncio
    async def test_get_current_user_id_with_valid_token_data_should_return_user_id(self):
        token_data = {"user_id": "test-user-123", "valid": True}

        result = await get_current_user_id(token_data)

        assert result == "test-user-123"

    @pytest.mark.asyncio
    async def test_get_current_user_id_with_missing_user_id_should_raise_http_exception(self):
        token_data = {"valid": True}

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(token_data)

        assert exc_info.value.status_code == 401
        assert "User ID not found" in exc_info.value.detail


class TestVideoProcessingEndpoints:

    @pytest.mark.asyncio
    async def test_submit_video_for_processing_with_valid_input_should_return_success(
            self, mock_upload_file, mock_controller, mock_user_service
    ):
        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import submit_video_for_processing

                result = await submit_video_for_processing(
                    video_file=mock_upload_file,
                    extraction_fps=2.0,
                    output_format="png",
                    quality=90,
                    start_time=0.0,
                    end_time=None,
                    max_frames=None,
                    controller=mock_controller,
                    current_user_id="test-user-123"
                )

                assert result["success"] is True
                mock_controller.submit_video_for_processing.assert_called_once()
                mock_user_service.verify_user_exists.assert_called_once_with("test-user-123")

    @pytest.mark.asyncio
    async def test_submit_video_for_processing_with_nonexistent_user_should_raise_http_exception(
            self, mock_upload_file, mock_controller, mock_user_service
    ):
        mock_user_service.verify_user_exists = AsyncMock(return_value=False)

        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import submit_video_for_processing

                with pytest.raises(HTTPException) as exc_info:
                    await submit_video_for_processing(
                        video_file=mock_upload_file,
                        extraction_fps=2.0,
                        output_format="png",
                        quality=90,
                        start_time=0.0,
                        end_time=None,
                        max_frames=None,
                        controller=mock_controller,
                        current_user_id="test-user-123"
                    )

                assert exc_info.value.status_code == 404
                assert "not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_job_status_with_valid_job_should_return_status(
            self, mock_controller, mock_user_service
    ):
        expected_status = {
            "success": True,
            "data": {"status": "completed", "job_data": {"id": "test-job-id"}}
        }
        mock_controller.get_job_status = AsyncMock(return_value=expected_status)

        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import get_job_status

                result = await get_job_status(
                    job_id="test-job-id",
                    controller=mock_controller,
                    current_user_id="test-user-123"
                )

                assert result == expected_status
                mock_controller.get_job_status.assert_called_once_with("test-job-id", "test-user-123")

    @pytest.mark.asyncio
    async def test_get_active_jobs_should_return_processing_jobs_with_progress(
            self, mock_controller, mock_user_service
    ):
        from domain.entities.video_job import JobStatus

        mock_controller.list_user_jobs = AsyncMock(return_value={
            "data": {
                "jobs": [
                    {
                        "id": "job-1",
                        "original_filename": "video1.mp4",
                        "status": "processing"
                    },
                    {
                        "id": "job-2",
                        "original_filename": "video2.mp4",
                        "status": "processing"
                    }
                ]
            }
        })

        mock_controller.get_job_status = AsyncMock(return_value={
            "job_data": {
                "metadata": {
                    "progress": {
                        "percentage": 75,
                        "message": "Packaging results",
                        "updated_at": "2023-01-01T12:00:00"
                    }
                },
                "processing_started_at": "2023-01-01T11:00:00"
            }
        })

        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import get_active_jobs

                result = await get_active_jobs(
                    current_user_id="test-user-123",
                    controller=mock_controller
                )

                assert result["total_active"] == 2
                assert len(result["active_jobs"]) == 2
                assert "processing_summary" in result

    @pytest.mark.asyncio
    async def test_list_user_jobs_with_status_filter_should_filter_correctly(
            self, mock_controller, mock_user_service
    ):
        expected_response = {
            "success": True,
            "data": {"jobs": [], "pagination": {}}
        }
        mock_controller.list_user_jobs = AsyncMock(return_value=expected_response)

        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import list_user_jobs
                from domain.entities.video_job import JobStatus

                result = await list_user_jobs(
                    status_filter="completed",
                    skip=0,
                    limit=20,
                    current_user_id="test-user-123",
                    controller=mock_controller
                )

                assert result == expected_response
                mock_controller.list_user_jobs.assert_called_once()
                call_args = mock_controller.list_user_jobs.call_args[1]
                assert call_args["status_filter"] == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_list_user_jobs_with_invalid_status_filter_should_raise_http_exception(
            self, mock_controller, mock_user_service
    ):
        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import list_user_jobs

                with pytest.raises(HTTPException) as exc_info:
                    await list_user_jobs(
                        status_filter="invalid_status",
                        skip=0,
                        limit=20,
                        current_user_id="test-user-123",
                        controller=mock_controller
                    )

                assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_download_processing_result_with_existing_file_should_return_file_response(
            self, mock_controller, mock_user_service
    ):
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
            temp_file.write(b"fake zip content")
            temp_file_path = temp_file.name

        try:
            mock_controller.download_processing_result = AsyncMock(return_value={
                "data": {
                    "download": {
                        "file_path": temp_file_path,
                        "filename": "test_frames.zip",
                        "file_size_mb": 1.0,
                        "job_info": {
                            "frame_count": 50,
                            "processing_completed_at": "2023-01-01T12:00:00"
                        }
                    }
                }
            })

            mock_controller.get_job_status = AsyncMock(return_value={
                "job_data": {"zip_file_path": temp_file_path}
            })

            with patch('api.video_processing_router.get_video_processing_controller',
                       return_value=mock_controller):
                with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                    from api.video_processing_router import download_processing_result

                    result = await download_processing_result(
                        job_id="test-job-id",
                        include_metadata=False,
                        controller=mock_controller,
                        current_user_id="test-user-123"
                    )

                    assert isinstance(result, FileResponse)
                    assert result.media_type == "application/zip"

        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    @pytest.mark.asyncio
    async def test_download_processing_result_with_missing_file_should_raise_http_exception(
            self, mock_controller, mock_user_service
    ):
        mock_controller.download_processing_result = AsyncMock(return_value={
            "data": {
                "download": {
                    "file_path": "/nonexistent/path.zip",
                    "filename": "test_frames.zip"
                }
            }
        })

        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import download_processing_result

                with pytest.raises(HTTPException) as exc_info:
                    await download_processing_result(
                        job_id="test-job-id",
                        include_metadata=False,
                        controller=mock_controller,
                        current_user_id="test-user-123"
                    )

                assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_video_job_with_valid_job_should_return_success(
            self, mock_controller, mock_user_service
    ):
        expected_response = {
            "success": True,
            "message": "Job deleted successfully"
        }
        mock_controller.delete_video_job = AsyncMock(return_value=expected_response)

        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import delete_video_job

                result = await delete_video_job(
                    job_id="test-job-id",
                    delete_files=True,
                    controller=mock_controller,
                    current_user_id="test-user-123"
                )

                assert result == expected_response
                mock_controller.delete_video_job.assert_called_once_with(
                    job_id="test-job-id",
                    user_id="test-user-123",
                    delete_files=True
                )

    @pytest.mark.asyncio
    async def test_cancel_processing_job_with_processing_job_should_return_success(
            self, mock_controller, mock_user_service
    ):
        mock_controller.get_job_status = AsyncMock(return_value={
            "status": "processing"
        })

        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import cancel_processing_job

                result = await cancel_processing_job(
                    job_id="test-job-id",
                    controller=mock_controller,
                    current_user_id="test-user-123"
                )

                assert result["status"] == "cancelled"
                assert "cancellation requested" in result["message"]

    @pytest.mark.asyncio
    async def test_cancel_processing_job_with_completed_job_should_raise_http_exception(
            self, mock_controller, mock_user_service
    ):
        mock_controller.get_job_status = AsyncMock(return_value={
            "status": "completed"
        })

        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import cancel_processing_job

                with pytest.raises(HTTPException) as exc_info:
                    await cancel_processing_job(
                        job_id="test-job-id",
                        controller=mock_controller,
                        current_user_id="test-user-123"
                    )

                assert exc_info.value.status_code == 400
                assert "Cannot cancel" in exc_info.value.detail


    @pytest.mark.asyncio
    async def test_get_system_statistics_should_return_stats(self, mock_user_service):
        with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
            from api.video_processing_router import get_system_statistics

            result = await get_system_statistics(current_user_id="test-user-123")

            assert "processing_stats" in result
            assert "queue_stats" in result
            assert "system_resources" in result

    @pytest.mark.asyncio
    async def test_get_user_processing_preferences_should_return_preferences(self, mock_user_service):
        expected_preferences = {
            "processing": {"default_quality": 95, "default_fps": 1.0}
        }
        mock_user_service.get_user_preferences = AsyncMock(return_value=expected_preferences)

        with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
            from api.video_processing_router import get_user_processing_preferences

            result = await get_user_processing_preferences(current_user_id="test-user-123")

            assert result == expected_preferences

    @pytest.mark.asyncio
    async def test_update_user_processing_preferences_should_record_activity(self, mock_user_service):
        preferences = {"processing": {"default_quality": 90}}

        with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
            from api.video_processing_router import update_user_processing_preferences

            result = await update_user_processing_preferences(
                preferences=preferences,
                current_user_id="test-user-123"
            )

            assert result["message"] == "Processing preferences updated successfully"
            mock_user_service.update_user_activity.assert_called_once()


class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_endpoint_with_user_service_exception_should_raise_http_exception(
            self, mock_controller, mock_user_service
    ):
        from infra.gateways.user_service_gateway import UserServiceException

        mock_user_service.verify_user_exists = AsyncMock(
            side_effect=UserServiceException("Service error")
        )

        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import get_job_status

                with pytest.raises(HTTPException) as exc_info:
                    await get_job_status(
                        job_id="test-job-id",
                        controller=mock_controller,
                        current_user_id="test-user-123"
                    )

                assert exc_info.value.status_code == 400
                assert "User service error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_endpoint_with_generic_exception_should_return_internal_server_error(
            self, mock_controller, mock_user_service
    ):
        mock_user_service.verify_user_exists = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import get_job_status

                with pytest.raises(HTTPException) as exc_info:
                    await get_job_status(
                        job_id="test-job-id",
                        controller=mock_controller,
                        current_user_id="test-user-123"
                    )

                assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_download_with_controller_exception_should_handle_error_appropriately(
            self, mock_controller, mock_user_service
    ):
        mock_controller.download_processing_result = AsyncMock(
            side_effect=Exception("Job not found")
        )

        with patch('api.video_processing_router.get_video_processing_controller',
                   return_value=mock_controller):
            with patch('api.video_processing_router.get_user_service', return_value=mock_user_service):
                from api.video_processing_router import download_processing_result

                with pytest.raises(HTTPException) as exc_info:
                    await download_processing_result(
                        job_id="test-job-id",
                        include_metadata=False,
                        controller=mock_controller,
                        current_user_id="test-user-123"
                    )

                assert exc_info.value.status_code == 404
                assert "not found" in exc_info.value.detail.lower()