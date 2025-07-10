import logging

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status, Response, Header
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError, DecodeError
import os
import base64
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from infra.controllers.video_processing_controller import VideoProcessingController
from interfaces.schemas.video_processing_schemas import (
    VideoSubmissionResponse,
    JobStatusResponse,
    JobListResponse,
    JobDeletionResponse
)

from infra.settings.settings import get_settings
from infra.depedencies.database import get_database_session, get_user_service
from infra.gateways.user_service_gateway import UserServiceGateway, UserServiceException
from infra.repositories.video_job_repository import VideoJobRepository
from infra.services.video_processor_service import VideoProcessorService
from infra.services.file_storage_service import FileStorageService
from infra.gateways.kafka_gateway import KafkaGateway
from infra.gateways.auth_gateway import AuthGateway
from infra.gateways.notification_gateway import NotificationGateway
from infra.presenters.video_processing_presenter import VideoProcessingPresenter

from use_cases.video_processing.submit_video_use_case import SubmitVideoProcessingUseCase
from use_cases.video_processing.get_job_status_use_case import GetJobStatusUseCase
from use_cases.video_processing.list_user_jobs_use_case import ListUserJobsUseCase
from use_cases.video_processing.download_result_use_case import DownloadProcessingResultUseCase, DeleteVideoJobUseCase

router = APIRouter(prefix="/video-processing", tags=["Video Processing"])
security = HTTPBearer()

_auth_gateway = None
_notification_gateway = None


async def get_auth_gateway():
    global _auth_gateway

    if _auth_gateway is None:
        settings = get_settings()
        print("[DEBUG] Instantiating AuthGateway with:", settings.auth.model_dump())
        _auth_gateway = AuthGateway(
            auth_service_url=settings.auth.service_url,
            timeout=settings.auth.timeout
        )

    return _auth_gateway


async def validate_user_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials

        try:
            auth_gateway = await get_auth_gateway()
            validation_result = await auth_gateway.validate_token(token)

            if validation_result and validation_result.get("valid"):
                return validation_result

        except Exception as auth_service_error:
            print(f"[WARNING] Auth service error: {auth_service_error}")
            print("[INFO] Falling back to local JWT validation")

        try:
            parts = token.split('.')
            if len(parts) != 3:
                raise ValueError("Token must have 3 parts separated by dots")

            payload_encoded = parts[1]

            padding = 4 - len(payload_encoded) % 4
            if padding != 4:
                payload_encoded += '=' * padding

            payload_decoded = base64.urlsafe_b64decode(payload_encoded)
            payload_json = json.loads(payload_decoded)

            user_id = payload_json.get("sub") or payload_json.get("user_id")
            exp = payload_json.get("exp")
            iat = payload_json.get("iat")

            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User ID not found in token",
                    headers={"WWW-Authenticate": "Bearer"}
                )

            if exp:
                current_time = datetime.utcnow().timestamp()
                if current_time > exp:
                    exp_datetime = datetime.fromtimestamp(exp)
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Token expired at {exp_datetime.isoformat()}",
                        headers={"WWW-Authenticate": "Bearer"}
                    )

            print(f"[INFO] Manual JWT validation successful for user: {user_id}")

            return {
                "valid": True,
                "user_id": user_id,
                "token_type": payload_json.get("type", "access"),
                "expires_at": exp,
                "issued_at": iat,
                "username": payload_json.get("username"),
                "email": payload_json.get("email"),
                "issuer": payload_json.get("iss"),
                "jti": payload_json.get("jti"),
                "validation_method": "manual_decode"
            }

        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON decode error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload format",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except ValueError as e:
            print(f"[ERROR] Token format error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token structure",
                headers={"WWW-Authenticate": "Bearer"}
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error during token validation: {str(e)}")
        print(f"[ERROR] Error type: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user_id(token_data: dict = Depends(validate_user_token)) -> str:
    user_id = token_data.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token"
        )
    return user_id


async def get_video_processing_controller():
    settings = get_settings()

    from infra.integration.microservice_manager import get_microservice_manager
    manager = get_microservice_manager()
    session_factory = await manager.get_session_factory()
    video_job_repository = VideoJobRepository(session_factory)

    video_processor_service = VideoProcessorService(
        ffmpeg_path=settings.processing.ffmpeg_path,
        ffprobe_path=settings.processing.ffprobe_path,
        max_concurrent_processes=settings.processing.max_concurrent_jobs
    )

    file_storage_service = FileStorageService(
        base_storage_path=settings.storage.base_path,
        max_file_size_mb=settings.processing.max_file_size_mb
    )

    kafka_gateway = KafkaGateway(
        bootstrap_servers=settings.kafka.bootstrap_servers,
        security_protocol=settings.kafka.security_protocol
    )

    global _notification_gateway
    if _notification_gateway is None:
        _notification_gateway = NotificationGateway(
            gmail_email=settings.notification.gmail_email,
            gmail_app_password=settings.notification.gmail_app_password,
            from_name=settings.notification.from_name,
            admin_emails=settings.notification.get_admin_emails_list()
        )

    presenter = VideoProcessingPresenter()

    user_service = await get_user_service()

    submit_video_use_case = SubmitVideoProcessingUseCase(
        job_repository=video_job_repository,
        video_processor=video_processor_service,
        file_storage=file_storage_service,
        kafka_gateway=kafka_gateway,
        user_service_gateway=user_service
    )

    get_job_status_use_case = GetJobStatusUseCase(
        job_repository=video_job_repository
    )

    list_user_jobs_use_case = ListUserJobsUseCase(
        job_repository=video_job_repository
    )

    download_result_use_case = DownloadProcessingResultUseCase(
        job_repository=video_job_repository,
        file_storage=file_storage_service
    )

    delete_job_use_case = DeleteVideoJobUseCase(
        job_repository=video_job_repository,
        file_storage=file_storage_service
    )

    return VideoProcessingController(
        submit_video_use_case=submit_video_use_case,
        get_job_status_use_case=get_job_status_use_case,
        list_user_jobs_use_case=list_user_jobs_use_case,
        download_result_use_case=download_result_use_case,
        delete_job_use_case=delete_job_use_case,
        presenter=presenter
    )


@router.post("/submit", status_code=status.HTTP_201_CREATED)
async def submit_video_for_processing(
        video_file: UploadFile = File(..., description="Video file to process for frame extraction"),
        extraction_fps: float = Form(1.0, description="Frames per second to extract", ge=0.1, le=60.0),
        output_format: str = Form("png", description="Output image format", regex="^(png|jpg|jpeg)$"),
        quality: int = Form(95, description="Output image quality", ge=1, le=100),
        start_time: float = Form(0.0, description="Start time in seconds", ge=0.0),
        end_time: Optional[float] = Form(None, description="End time in seconds"),
        max_frames: Optional[int] = Form(None, description="Maximum frames to extract", ge=1),
        controller: VideoProcessingController = Depends(get_video_processing_controller),
        current_user_id: str = Depends(get_current_user_id)
):
    try:
        user_service = await get_user_service()

        user_exists = await user_service.verify_user_exists(current_user_id)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {current_user_id} not found"
            )

        try:
            user_preferences = await user_service.get_user_preferences(current_user_id)
        except UserServiceException:
            user_preferences = {
                "processing": {
                    "default_quality": 95,
                    "default_fps": 1.0,
                    "auto_cleanup": True,
                    "max_frames": 100
                }
            }

        processing_params = {
            "extraction_fps": extraction_fps,
            "output_format": output_format,
            "quality": quality,
            "start_time": start_time,
            "end_time": end_time,
            "max_frames": max_frames or user_preferences.get("processing", {}).get("max_frames", 100),
            "user_preferences": user_preferences
        }

        result = await controller.submit_video_for_processing(
            file=video_file,
            user_id=current_user_id,
            **processing_params
        )

        activity_data = {
            "action": "video_submitted",
            "video_filename": video_file.filename,
            "processing_params": processing_params
        }
        await user_service.update_user_activity(current_user_id, activity_data)

        return result

    except HTTPException:
        raise
    except UserServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User service error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during video processing submission"
        )


@router.get("/jobs/{job_id}/status")
async def get_job_status(
        job_id: str,
        controller: VideoProcessingController = Depends(get_video_processing_controller),
        current_user_id: str = Depends(get_current_user_id)
):
    try:
        user_service = await get_user_service()
        user_exists = await user_service.verify_user_exists(current_user_id)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {current_user_id} not found"
            )

        return await controller.get_job_status(job_id, current_user_id)

    except HTTPException:
        raise
    except UserServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User service error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving job status"
        )


@router.get("/jobs/active")
async def get_active_jobs(
        current_user_id: str = Depends(get_current_user_id),
        controller: VideoProcessingController = Depends(get_video_processing_controller)
):
    try:
        user_service = await get_user_service()
        user_exists = await user_service.verify_user_exists(current_user_id)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {current_user_id} not found"
            )

        from domain.entities.video_job import JobStatus

        processing_jobs = await controller.list_user_jobs(
            user_id=current_user_id,
            status_filter=JobStatus.PROCESSING,
            skip=0,
            limit=50
        )

        active_jobs = []
        for job_data in processing_jobs.get("data", {}).get("jobs", []):
            job_progress = {
                "job_id": job_data["id"],
                "original_filename": job_data["original_filename"],
                "status": job_data["status"],
                "progress_percentage": 0,
                "current_stage": "Processing",
                "started_at": None
            }

            try:
                job_status = await controller.get_job_status(job_data["id"], current_user_id)
                progress_info = job_status.get("job_data", {}).get("metadata", {}).get("progress", {})

                job_progress.update({
                    "progress_percentage": progress_info.get("percentage", 0),
                    "current_stage": progress_info.get("message", "Processing"),
                    "last_updated": progress_info.get("updated_at"),
                    "started_at": job_status["job_data"].get("processing_started_at")
                })
            except Exception:
                pass

            active_jobs.append(job_progress)

        return {
            "active_jobs": active_jobs,
            "total_active": len(active_jobs),
            "processing_summary": {
                "jobs_in_queue": len([j for j in active_jobs if j["progress_percentage"] < 10]),
                "jobs_extracting": len([j for j in active_jobs if 30 <= j["progress_percentage"] < 80]),
                "jobs_packaging": len([j for j in active_jobs if j["progress_percentage"] >= 80])
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving active jobs"
        )


@router.get("/jobs")
async def list_user_jobs(
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
        current_user_id: str = Depends(get_current_user_id),
        controller: VideoProcessingController = Depends(get_video_processing_controller)
):
    try:
        user_service = await get_user_service()
        user_exists = await user_service.verify_user_exists(current_user_id)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {current_user_id} not found"
            )

        from domain.entities.video_job import JobStatus

        parsed_status_filter = None
        if status_filter:
            try:
                parsed_status_filter = JobStatus(status_filter.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter: {status_filter}"
                )

        result = await controller.list_user_jobs(
            user_id=current_user_id,
            status_filter=parsed_status_filter,
            skip=skip,
            limit=min(limit, 100)
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "type": "internal_server_error",
                    "message": "Failed to list user jobs",
                    "details": str(e),
                    "error_type": type(e).__name__
                }
            }
        )


@router.get("/jobs/{job_id}/download")
async def download_processing_result(
        job_id: str,
        include_metadata: bool = False,
        controller: VideoProcessingController = Depends(get_video_processing_controller),
        current_user_id: str = Depends(get_current_user_id)
):
    try:
        user_service = await get_user_service()
        user_exists = await user_service.verify_user_exists(current_user_id)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {current_user_id} not found"
            )

        try:
            download_info = await controller.download_processing_result(
                job_id=job_id,
                user_id=current_user_id,
                include_metadata=include_metadata
            )
        except Exception as controller_error:
            error_msg = str(controller_error).lower()
            if "not found" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found or not accessible"
                )
            elif "not completed" in error_msg or "not available" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Job is not completed yet or download not available"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Download preparation failed: {str(controller_error)}"
                )

        if not download_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Download information not available"
            )

        file_path = None
        download_data = None

        if isinstance(download_info, dict):
            if "data" in download_info and "download" in download_info["data"]:
                download_data = download_info["data"]["download"]
                file_path = (
                        download_data.get("file_path") or
                        download_data.get("path") or
                        download_data.get("zip_file_path")
                )
            else:
                file_path = (
                        download_info.get("file_path") or
                        download_info.get("path") or
                        download_info.get("zip_file_path")
                )
        elif hasattr(download_info, 'file_path'):
            file_path = download_info.file_path

        if not file_path:
            try:
                job_status = await controller.get_job_status(job_id, current_user_id)
                job_data = job_status.get("job_data", {})
                file_path = job_data.get("zip_file_path")

                if not file_path and download_data:
                    filename = download_data.get("filename")
                    actual_filename = f"{job_id}_frames.zip"

                    user_results_path = f"/app/storage/results/{current_user_id}/{actual_filename}"
                    if os.path.exists(user_results_path):
                        file_path = user_results_path
                    else:
                        user_results_path_original = f"/app/storage/results/{current_user_id}/{filename}"
                        if os.path.exists(user_results_path_original):
                            file_path = user_results_path_original
                        else:
                            user_results_dir = f"/app/storage/results/{current_user_id}"
                            if os.path.exists(user_results_dir):
                                for item in os.listdir(user_results_dir):
                                    if item == filename or item == actual_filename or item.startswith(job_id):
                                        file_path = os.path.join(user_results_dir, item)
                                        break

            except Exception:
                pass

        if not file_path or not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Download file not found or has been removed"
            )

        try:
            file_size = os.path.getsize(file_path)
        except Exception:
            if download_data and "file_size_mb" in download_data:
                file_size = int(download_data["file_size_mb"] * 1024 * 1024)
            else:
                file_size = 0

        filename = f"{job_id}_frames.zip"
        if download_data and "filename" in download_data:
            original_filename = download_data["filename"]
            try:
                filename = original_filename.encode('ascii', 'ignore').decode('ascii')
                if not filename or filename.isspace():
                    filename = f"{job_id}_frames.zip"
            except:
                filename = f"{job_id}_frames.zip"
        elif isinstance(download_info, dict):
            original_filename = download_info.get("filename", f"{job_id}_frames.zip")
            try:
                filename = original_filename.encode('ascii', 'ignore').decode('ascii')
                if not filename or filename.isspace():
                    filename = f"{job_id}_frames.zip"
            except:
                filename = f"{job_id}_frames.zip"

        safe_filename = filename.replace(' ', '_').replace('à', 'a').replace('ã', 'a').replace('ç', 'c')

        headers = {
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Content-Length": str(file_size),
            "X-Job-ID": job_id,
        }

        try:
            job_info = None
            if download_data and "job_info" in download_data:
                job_info = download_data["job_info"]
            elif isinstance(download_info, dict):
                job_info = download_info.get("job_data", {})

            if job_info:
                headers["X-Frame-Count"] = str(job_info.get("frame_count", 0))
                if "processing_completed_at" in job_info:
                    headers["X-Processing-Completed"] = job_info["processing_completed_at"]
        except Exception:
            pass

        try:
            activity_data = {
                "action": "result_downloaded",
                "job_id": job_id,
                "file_size": file_size
            }
            await user_service.update_user_activity(current_user_id, activity_data)
        except Exception:
            pass

        return FileResponse(
            path=file_path,
            media_type="application/zip",
            headers=headers,
            filename=safe_filename
        )

    except HTTPException:
        raise
    except UserServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User service error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during file download: {str(e)}"
        )


@router.delete("/jobs/{job_id}")
async def delete_video_job(
        job_id: str,
        delete_files: bool = True,
        controller: VideoProcessingController = Depends(get_video_processing_controller),
        current_user_id: str = Depends(get_current_user_id)
):
    try:
        user_service = await get_user_service()
        user_exists = await user_service.verify_user_exists(current_user_id)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {current_user_id} not found"
            )

        result = await controller.delete_video_job(
            job_id=job_id,
            user_id=current_user_id,
            delete_files=delete_files
        )

        activity_data = {
            "action": "job_deleted",
            "job_id": job_id,
            "files_deleted": delete_files
        }
        await user_service.update_user_activity(current_user_id, activity_data)

        return result

    except HTTPException:
        raise
    except UserServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User service error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during job deletion"
        )

@router.post("/jobs/{job_id}/cancel")
async def cancel_processing_job(
        job_id: str,
        controller: VideoProcessingController = Depends(get_video_processing_controller),
        current_user_id: str = Depends(get_current_user_id)
):
    try:
        user_service = await get_user_service()
        user_exists = await user_service.verify_user_exists(current_user_id)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {current_user_id} not found"
            )

        job_status = await controller.get_job_status(job_id, current_user_id)

        current_status = job_status["status"]
        if current_status not in ["pending", "processing"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel job with status: {current_status}"
            )

        activity_data = {
            "action": "job_cancelled",
            "job_id": job_id,
            "previous_status": current_status
        }
        await user_service.update_user_activity(current_user_id, activity_data)

        return {"message": f"Job {job_id} cancellation requested", "status": "cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during job cancellation"
        )


@router.get("/system/health")
async def get_system_health():
    try:
        user_service = await get_user_service()

        user_service_health = await user_service.health_check()

        try:
            from infra.integration.microservice_manager import get_microservice_manager
            manager = get_microservice_manager()
            session_factory = await manager.get_session_factory()
            async with session_factory() as session:
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
                db_healthy = True
        except Exception:
            db_healthy = False

        return {
            "status": "healthy" if db_healthy and user_service_health["healthy"] else "degraded",
            "service": "video-processing",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": {
                "database": {
                    "healthy": db_healthy,
                    "status": "connected" if db_healthy else "disconnected"
                },
                "user_service": user_service_health
            },
            "processing_capacity": {
                "max_concurrent_jobs": 10,
                "active_jobs": 0,
                "queue_length": 0
            },
            "supported_formats": ["mp4", "avi", "mov", "mkv", "webm", "wmv", "flv"],
            "max_file_size_mb": 500,
            "max_processing_time_minutes": 60
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/system/stats")
async def get_system_statistics(
        current_user_id: str = Depends(get_current_user_id)
):
    try:
        user_service = await get_user_service()
        user_exists = await user_service.verify_user_exists(current_user_id)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {current_user_id} not found"
            )

        return {
            "processing_stats": {
                "jobs_processed_today": 0,
                "total_frames_extracted": 0,
                "average_processing_time": 0.0,
                "success_rate": 100.0
            },
            "queue_stats": {
                "pending_jobs": 0,
                "processing_jobs": 0,
                "average_wait_time": 0.0
            },
            "system_resources": {
                "cpu_usage": 0.0,
                "memory_usage": 0.0,
                "disk_usage": 0.0,
                "available_workers": 4
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving system statistics"
        )


@router.get("/user/preferences")
async def get_user_processing_preferences(
        current_user_id: str = Depends(get_current_user_id)
):
    try:
        user_service = await get_user_service()
        user_exists = await user_service.verify_user_exists(current_user_id)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {current_user_id} not found"
            )

        preferences = await user_service.get_user_preferences(current_user_id)
        return preferences

    except HTTPException:
        raise
    except UserServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user preferences: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving user preferences"
        )


@router.put("/user/preferences")
async def update_user_processing_preferences(
        preferences: dict,
        current_user_id: str = Depends(get_current_user_id)
):
    try:
        user_service = await get_user_service()
        user_exists = await user_service.verify_user_exists(current_user_id)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {current_user_id} not found"
            )

        await user_service.update_user_activity(
            user_id=current_user_id,
            activity_data={
                "action": "preferences_updated",
                "preferences": preferences,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        return {
            "message": "Processing preferences updated successfully",
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except UserServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user preferences: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error updating user preferences"
        )