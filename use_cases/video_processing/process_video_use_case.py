import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
import os
import zipfile
import tempfile

from interfaces.repositories.video_job_repository_interface import VideoJobRepositoryInterface
from interfaces.services.video_processor_interface import VideoProcessorInterface
from interfaces.services.file_storage_interface import FileStorageInterface
from interfaces.gateways.notification_gateway_interface import NotificationGatewayInterface
from infra.gateways.user_service_gateway import UserServiceGateway

from domain.entities.video_job import VideoJob, JobStatus
from domain.value_objects import VideoFile, FrameExtractionConfig
from domain.exceptions import ProcessingException, VideoJobNotFoundException


@dataclass
class ProcessVideoRequest:
    """
    Request object for video processing use case.

    Contains the job identifier and worker information needed
    to execute video frame extraction processing.

    Attributes:
        job_id: Unique identifier of the video job to process
        worker_id: Identifier of the worker processing this job
    """
    job_id: str
    worker_id: str


@dataclass
class ProcessVideoResponse:
    """
    Response object for video processing use case.

    Contains the result of video processing operation including
    success status, extracted frame information, and error details.

    Attributes:
        success: Whether the processing completed successfully
        job_id: Identifier of the processed job
        frame_count: Number of frames extracted
        zip_file_path: Path to the ZIP file containing extracted frames
        zip_file_size: Size of the ZIP file in bytes
        processing_duration: Processing time in seconds
        error_message: Error message if processing failed
    """
    success: bool
    job_id: str
    frame_count: Optional[int] = None
    zip_file_path: Optional[str] = None
    zip_file_size: Optional[int] = None
    processing_duration: Optional[float] = None
    error_message: Optional[str] = None


class ProcessVideoUseCase:
    """
    Use case for processing video files and extracting frames.

    This use case handles the complete video processing workflow including
    job validation, frame extraction, result packaging, and status updates
    with comprehensive error handling and resource cleanup.

    It coordinates between video processing services, file storage, and
    notification systems to provide reliable video frame extraction
    capabilities with proper job lifecycle management.
    """

    def __init__(self,
                 job_repository: VideoJobRepositoryInterface,
                 video_processor: VideoProcessorInterface,
                 file_storage: FileStorageInterface,
                 notification_gateway: NotificationGatewayInterface,
                 user_service_gateway: UserServiceGateway):
        """
        Initialize the process video use case.

        Args:
            job_repository: Repository for video job data operations
            video_processor: Service for video processing and frame extraction
            file_storage: Service for file storage operations
            notification_gateway: Gateway for sending notifications
            user_service_gateway: Gateway for user service integration
        """
        self.job_repository = job_repository
        self.video_processor = video_processor
        self.file_storage = file_storage
        self.notification_gateway = notification_gateway
        self.user_service_gateway = user_service_gateway

    async def execute(self, request: ProcessVideoRequest) -> ProcessVideoResponse:
        """
        Execute video processing workflow with comprehensive error handling.

        Performs the complete video processing pipeline including job validation,
        status updates, frame extraction, result packaging, and cleanup with
        detailed logging and error recovery mechanisms.

        Args:
            request: Processing request with job ID and worker information

        Returns:
            ProcessVideoResponse: Processing result with success status and details

        Raises:
            VideoJobNotFoundException: If the specified job cannot be found
            ProcessingException: If processing fails due to system errors
        """
        processing_start_time = datetime.utcnow()

        try:
            job = await self._get_and_validate_job(request.job_id)

            await self._update_job_status_to_processing(job, request.worker_id)
            await self._update_progress(job, 10, "Starting video processing")

            video_file = await self._prepare_video_file(job)
            await self._update_progress(job, 20, "Video file prepared")

            extraction_config = await self._prepare_extraction_config(job)
            await self._update_progress(job, 30, "Extraction configuration ready")

            frames_directory = await self._extract_frames(video_file, extraction_config, job)
            await self._update_progress(job, 80, "Frame extraction completed")

            zip_file_path, zip_file_size, frame_count = await self._package_results(
                frames_directory, job
            )
            await self._update_progress(job, 95, "Results packaging completed")

            await self._update_job_completion(
                job, zip_file_path, zip_file_size, frame_count, processing_start_time
            )

            await self._send_completion_notification(job)
            await self._update_progress(job, 100, "Processing completed successfully")

            processing_duration = (datetime.utcnow() - processing_start_time).total_seconds()

            return ProcessVideoResponse(
                success=True,
                job_id=job.id,
                frame_count=frame_count,
                zip_file_path=zip_file_path,
                zip_file_size=zip_file_size,
                processing_duration=processing_duration
            )

        except Exception as e:
            await self._handle_processing_error(request.job_id, str(e))
            processing_duration = (datetime.utcnow() - processing_start_time).total_seconds()

            return ProcessVideoResponse(
                success=False,
                job_id=request.job_id,
                processing_duration=processing_duration,
                error_message=str(e)
            )

    async def _get_and_validate_job(self, job_id: str) -> VideoJob:
        """
        Retrieve and validate the video job for processing.

        Args:
            job_id: Unique identifier of the job to retrieve

        Returns:
            VideoJob: Retrieved and validated job entity

        Raises:
            VideoJobNotFoundException: If job cannot be found
            ProcessingException: If job is in invalid state for processing
        """
        job = await self.job_repository.find_by_id(job_id)
        if not job:
            raise VideoJobNotFoundException(job_id)

        if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
            raise ProcessingException(
                f"Job {job_id} is not in a processable state: {job.status}"
            )

        return job

    async def _update_job_status_to_processing(self, job: VideoJob, worker_id: str) -> None:
        """
        Update job status to processing with worker information.

        Args:
            job: Video job to update
            worker_id: Identifier of the worker processing this job
        """
        job.status = JobStatus.PROCESSING
        job.processing_started_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()

        if not job.metadata:
            job.metadata = {}
        job.metadata["worker_id"] = worker_id

        await self.job_repository.update(job)

    async def _prepare_video_file(self, job: VideoJob) -> VideoFile:
        """
        Prepare video file object for processing.

        Args:
            job: Video job containing file information

        Returns:
            VideoFile: Video file object ready for processing
        """
        return VideoFile(
            file_path=job.file_path,
            original_name=job.original_filename,
            size_bytes=job.file_size
        )

    async def _prepare_extraction_config(self, job: VideoJob) -> FrameExtractionConfig:
        """
        Prepare frame extraction configuration from job metadata.

        Args:
            job: Video job containing extraction parameters

        Returns:
            FrameExtractionConfig: Configuration for frame extraction
        """
        extraction_metadata = job.metadata.get("extraction_config", {})

        return FrameExtractionConfig(
            fps=job.extraction_fps or 1.0,
            output_format=extraction_metadata.get("output_format", "png"),
            quality=extraction_metadata.get("quality", 95),
            start_time=extraction_metadata.get("start_time", 0.0),
            end_time=extraction_metadata.get("end_time"),
            max_frames=extraction_metadata.get("max_frames")
        )

    async def _update_progress(self, job: VideoJob, percentage: int, message: str) -> None:
        """
        Update job progress information in metadata.

        Args:
            job: Video job to update
            percentage: Progress percentage (0-100)
            message: Progress message description
        """
        try:
            if not job.metadata:
                job.metadata = {}

            job.metadata["progress"] = {
                "percentage": percentage,
                "message": message,
                "updated_at": datetime.utcnow().isoformat()
            }

            job.updated_at = datetime.utcnow()
            await self.job_repository.update(job)

            print(f"Job {job.id} progress: {percentage}% - {message}")

        except Exception as e:
            print(f"Warning: Could not update progress for job {job.id}: {str(e)}")

    async def _extract_frames(self, video_file: VideoFile, config: FrameExtractionConfig, job: VideoJob) -> str:
        """
        Extract frames from video using the video processor service with progress tracking.

        Args:
            video_file: Video file to process
            config: Frame extraction configuration
            job: Video job for progress updates

        Returns:
            str: Path to directory containing extracted frames

        Raises:
            ProcessingException: If frame extraction fails
        """
        try:
            await self._update_progress(job, 35, "Starting frame extraction")

            result = await self.video_processor.extract_frames(video_file, config)

            if isinstance(result, list):
                if not result:
                    raise ProcessingException("No frames extracted from video")

                import os
                frames_directory = os.path.dirname(result[0])
                return frames_directory
            elif isinstance(result, str):
                return result
            else:
                raise ProcessingException(f"Unexpected result type from frame extraction: {type(result)}")

        except Exception as e:
            raise ProcessingException(f"Frame extraction failed: {str(e)}")

    async def _package_results(self, frames_directory: str, job: VideoJob) -> tuple[str, int, int]:
        """
        Package extracted frames into a ZIP file for download.

        Args:
            frames_directory: Directory containing extracted frame files
            job: Video job for naming and organization

        Returns:
            tuple: (zip_file_path, zip_file_size, frame_count)

        Raises:
            ProcessingException: If packaging fails
        """
        try:
            import tempfile
            import shutil

            zip_filename = f"{job.id}_frames.zip"

            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
                temp_zip_path = temp_zip.name

            frame_count = 0

            with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filename in os.listdir(frames_directory):
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                        file_path = os.path.join(frames_directory, filename)
                        zipf.write(file_path, filename)
                        frame_count += 1

            zip_file_size = os.path.getsize(temp_zip_path)

            try:
                with open(temp_zip_path, 'rb') as zip_file:
                    zip_content = zip_file.read()

                final_zip_path = await self.file_storage.store_file(
                    file_content=zip_content,
                    filename=zip_filename,
                    user_id=job.user_id
                )
            except AttributeError:
                try:
                    final_zip_path = await self.file_storage.store_video_file(
                        file_content=zip_content,
                        filename=zip_filename,
                        user_id=job.user_id
                    )
                except Exception as storage_error:
                    storage_dir = os.path.join("/app/storage", "results", job.user_id)
                    os.makedirs(storage_dir, exist_ok=True)
                    final_zip_path = os.path.join(storage_dir, zip_filename)
                    shutil.move(temp_zip_path, final_zip_path)
                    temp_zip_path = None

            if temp_zip_path and os.path.exists(temp_zip_path):
                os.unlink(temp_zip_path)

            shutil.rmtree(frames_directory, ignore_errors=True)

            return final_zip_path, zip_file_size, frame_count

        except Exception as e:
            raise ProcessingException(f"Result packaging failed: {str(e)}")

    async def _update_job_completion(self,
                                     job: VideoJob,
                                     zip_file_path: str,
                                     zip_file_size: int,
                                     frame_count: int,
                                     processing_start_time: datetime) -> None:
        """
        Update job with completion information.

        Args:
            job: Video job to update
            zip_file_path: Path to the created ZIP file
            zip_file_size: Size of the ZIP file in bytes
            frame_count: Number of frames extracted
            processing_start_time: When processing started
        """
        job.status = JobStatus.COMPLETED
        job.frame_count = frame_count
        job.zip_file_path = zip_file_path
        job.zip_file_size = zip_file_size
        job.processing_completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()

        if not job.metadata:
            job.metadata = {}

        job.metadata["processing_results"] = {
            "frames_extracted": frame_count,
            "zip_size_bytes": zip_file_size,
            "processing_duration": (job.processing_completed_at - processing_start_time).total_seconds(),
            "completed_at": job.processing_completed_at.isoformat()
        }

        await self.job_repository.update(job)

    async def _send_completion_notification(self, job: VideoJob) -> None:
        """
        Send completion notification to the user.

        Args:
            job: Completed video job
        """
        try:
            print(f"[NOTIFICATION] Starting completion notification for job {job.id}")

            user_info = await self.user_service_gateway.get_user_info(job.user_id)
            print(f"[NOTIFICATION] Retrieved user info: {user_info}")

            user_email = user_info.get("email")
            print(f"[NOTIFICATION] User email: {user_email}")

            if user_email and user_email != f"user_{job.user_id}@example.com":
                notification_data = {
                    "user_email": user_email,
                    "job_id": job.id,
                    "original_filename": job.original_filename,
                    "frame_count": job.frame_count,
                    "file_size_mb": job.get_file_size_mb(),
                    "processing_duration": job.get_processing_duration()
                }

                print(f"[NOTIFICATION] Sending notification with data: {notification_data}")

                success = await self.notification_gateway.send_job_completion_notification(
                    notification_data
                )

                print(f"[NOTIFICATION] Notification sent successfully: {success}")
            else:
                print(f"[NOTIFICATION] Skipping notification - no valid email found or using default email")

        except Exception as e:
            print(f"[NOTIFICATION] Warning: Failed to send completion notification: {str(e)}")
            import traceback
            traceback.print_exc()

    async def _handle_processing_error(self, job_id: str, error_message: str) -> None:
        """
        Handle processing errors by updating job status and sending notifications.

        Args:
            job_id: Identifier of the failed job
            error_message: Error message describing the failure
        """
        try:
            job = await self.job_repository.find_by_id(job_id)
            if job:
                job.status = JobStatus.FAILED
                job.error_message = error_message
                job.processing_completed_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()

                await self.job_repository.update(job)

                try:
                    print(f"[NOTIFICATION] Starting failure notification for job {job_id}")

                    user_info = await self.user_service_gateway.get_user_info(job.user_id)
                    print(f"[NOTIFICATION] Retrieved user info: {user_info}")

                    user_email = user_info.get("email")
                    print(f"[NOTIFICATION] User email: {user_email}")

                    if user_email and user_email != f"user_{job.user_id}@example.com":
                        notification_data = {
                            "user_email": user_email,
                            "job_id": job.id,
                            "original_filename": job.original_filename,
                            "error_message": error_message
                        }

                        print(f"[NOTIFICATION] Sending failure notification with data: {notification_data}")

                        success = await self.notification_gateway.send_job_failure_notification(
                            notification_data
                        )

                        print(f"[NOTIFICATION] Failure notification sent successfully: {success}")
                    else:
                        print(f"[NOTIFICATION] Skipping failure notification - no valid email found")

                except Exception as e:
                    print(f"[NOTIFICATION] Warning: Failed to send failure notification: {str(e)}")
                    import traceback
                    traceback.print_exc()

        except Exception as e:
            print(f"Error handling processing failure for job {job_id}: {str(e)}")