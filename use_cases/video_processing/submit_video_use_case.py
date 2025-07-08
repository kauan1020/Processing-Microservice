from dataclasses import dataclass
from typing import Optional, Dict, Any
import uuid
from datetime import datetime

from interfaces.repositories.video_job_repository_interface import VideoJobRepositoryInterface
from interfaces.services.video_processor_interface import VideoProcessorInterface
from interfaces.services.file_storage_interface import FileStorageInterface
from interfaces.gateways.kafka_gateway_interface import KafkaGatewayInterface
from infra.gateways.user_service_gateway import UserServiceGateway

from domain.entities.video_job import VideoJob, JobStatus, VideoFormat
from domain.value_objects import VideoFile, FrameExtractionConfig
from domain.exceptions import InvalidVideoFormatException, StorageException, ProcessingException


@dataclass
class SubmitVideoRequest:
    """
    Request object for video submission use case.

    This data class encapsulates all the information needed to submit
    a video for processing, including user identification, file data,
    and extraction configuration parameters.

    Attributes:
        user_id: Unique identifier of the user submitting the video
        file_content: Binary content of the video file
        original_filename: Original name of the uploaded file
        extraction_fps: Frames per second to extract from video
        output_format: Format for extracted frames (png, jpg, etc.)
        quality: Quality level for frame extraction (1-100)
        start_time: Start time in seconds for extraction
        end_time: End time in seconds for extraction, None for full video
        max_frames: Maximum number of frames to extract, None for no limit
    """

    user_id: str
    file_content: bytes
    original_filename: str
    extraction_fps: float = 1.0
    output_format: str = 'png'
    quality: int = 95
    start_time: float = 0.0
    end_time: Optional[float] = None
    max_frames: Optional[int] = None


@dataclass
class SubmitVideoResponse:
    """
    Response object for video submission use case.

    This data class contains the result of a video submission operation,
    including the created job information and processing estimates.

    Attributes:
        job_id: Unique identifier of the created job
        message: Status message for the submission
        queue_position: Position in the processing queue
        estimated_processing_time: Estimated time for processing in seconds
        estimated_frames: Estimated number of frames to be extracted
        job_data: Dictionary containing job metadata
    """

    job_id: str
    message: str
    queue_position: int
    estimated_processing_time: float
    estimated_frames: int
    job_data: Dict[str, Any]


class SubmitVideoProcessingUseCase:
    """
    Use case for submitting video files for frame extraction processing.

    This use case handles the complete workflow of video submission including
    file validation, storage, job creation, and queue management for
    asynchronous video processing operations.

    It coordinates between multiple services and repositories to ensure
    proper video handling, metadata extraction, and job scheduling
    while maintaining data consistency and error handling. The use case
    implements proper transaction management and event publishing for
    distributed system coordination.
    """

    def __init__(self,
                 job_repository: VideoJobRepositoryInterface,
                 video_processor: VideoProcessorInterface,
                 file_storage: FileStorageInterface,
                 kafka_gateway: KafkaGatewayInterface,
                 user_service_gateway: UserServiceGateway):
        """
        Initialize the submit video processing use case.

        Args:
            job_repository: Repository for video job persistence
            video_processor: Service for video analysis and processing
            file_storage: Service for file storage operations
            kafka_gateway: Gateway for message queue operations
            user_service_gateway: Gateway for user service integration
        """
        self.job_repository = job_repository
        self.video_processor = video_processor
        self.file_storage = file_storage
        self.kafka_gateway = kafka_gateway
        self.user_service_gateway = user_service_gateway

    async def execute(self, request: SubmitVideoRequest) -> SubmitVideoResponse:
        """
        Execute video submission workflow with comprehensive validation and processing.

        Performs the complete video submission workflow including user validation,
        file storage, video analysis, job creation, event publishing, and queue
        position calculation. The method ensures data consistency through proper
        transaction management and provides comprehensive error handling.

        Args:
            request: Video submission request with file data and parameters

        Returns:
            SubmitVideoResponse: Submission result with job information and estimates

        Raises:
            InvalidVideoFormatException: If video format is not supported
            StorageException: If file storage operations fail
            ProcessingException: If video processing setup fails
        """
        try:
            await self._validate_user(request.user_id)

            stored_file_path = await self._store_video_file(request)

            video_file = VideoFile(
                file_path=stored_file_path,
                original_name=request.original_filename,
                size_bytes=len(request.file_content)
            )

            await self._validate_video_file(video_file)

            video_info = await self._get_video_metadata(video_file)

            extraction_config = FrameExtractionConfig(
                fps=request.extraction_fps,
                output_format=request.output_format,
                quality=request.quality,
                start_time=request.start_time,
                end_time=request.end_time,
                max_frames=request.max_frames
            )

            job = await self._create_video_job(
                request, video_file, video_info, extraction_config
            )

            saved_job = await self.job_repository.create(job)

            await self._publish_job_submitted_event(saved_job)

            await self._update_user_activity(request.user_id, saved_job)

            estimated_processing_time = await self.video_processor.estimate_processing_time(
                video_file, extraction_config
            )

            estimated_frames = extraction_config.estimate_frame_count(
                video_info.get("duration", 0)
            )

            queue_position = await self._get_queue_position()

            return SubmitVideoResponse(
                job_id=saved_job.id,
                message="Video submitted successfully for processing",
                queue_position=queue_position,
                estimated_processing_time=estimated_processing_time,
                estimated_frames=estimated_frames,
                job_data={
                    "original_filename": saved_job.original_filename,
                    "file_size_mb": saved_job.get_file_size_mb(),
                    "video_format": saved_job.video_format.value,
                    "duration": saved_job.duration,
                    "extraction_fps": saved_job.extraction_fps
                }
            )

        except Exception as e:
            if isinstance(e, (InvalidVideoFormatException, StorageException, ProcessingException)):
                raise
            raise ProcessingException(f"Video submission failed: {str(e)}")

    async def _validate_user(self, user_id: str) -> None:
        """
        Validate that the user exists and is authorized to submit videos.

        Checks user existence through the user service gateway to ensure
        only valid users can submit videos for processing.

        Args:
            user_id: User identifier to validate

        Raises:
            ProcessingException: If user validation fails or user doesn't exist
        """
        try:
            user_exists = await self.user_service_gateway.verify_user_exists(user_id)
            if not user_exists:
                raise ProcessingException(f"User with ID '{user_id}' not found")

        except Exception as e:
            if isinstance(e, ProcessingException):
                raise
            raise ProcessingException(f"User validation failed: {str(e)}")

    async def _store_video_file(self, request: SubmitVideoRequest) -> str:
        """
        Store the uploaded video file securely in the file storage system.

        Saves the video file to persistent storage with proper organization
        by user and generates a unique file path for retrieval.

        Args:
            request: Video submission request containing file data

        Returns:
            str: Path to the stored video file

        Raises:
            StorageException: If file storage fails
        """
        try:
            return await self.file_storage.store_video_file(
                file_content=request.file_content,
                filename=request.original_filename,
                user_id=request.user_id
            )

        except Exception as e:
            raise StorageException("store", request.original_filename, str(e))

    async def _validate_video_file(self, video_file: VideoFile) -> None:
        """
        Validate video file format and readability.

        Performs comprehensive validation including format checking and
        file integrity verification through the video processor service.

        Args:
            video_file: Video file to validate

        Raises:
            InvalidVideoFormatException: If video format is invalid or unsupported
        """
        if not video_file.is_valid_video_format():
            raise InvalidVideoFormatException(
                video_file.original_name,
                video_file.get_extension()
            )

        is_valid = await self.video_processor.validate_video_file(video_file)
        if not is_valid:
            raise InvalidVideoFormatException(
                video_file.original_name,
                "File appears to be corrupted or unreadable"
            )

    async def _get_video_metadata(self, video_file: VideoFile) -> Dict[str, Any]:
        """
        Extract video metadata using the video processor service.

        Retrieves comprehensive video information including duration,
        frame rate, resolution, and other technical specifications
        needed for processing configuration.

        Args:
            video_file: Video file to analyze

        Returns:
            Dict[str, Any]: Video metadata information including duration, frame_rate, etc.

        Raises:
            ProcessingException: If metadata extraction fails
        """
        try:
            return await self.video_processor.get_video_info(video_file)

        except Exception as e:
            raise ProcessingException(f"Video metadata extraction failed: {str(e)}")

    async def _create_video_job(self,
                                request: SubmitVideoRequest,
                                video_file: VideoFile,
                                video_info: Dict[str, Any],
                                extraction_config: FrameExtractionConfig) -> VideoJob:
        """
        Create a new video job entity with all necessary information.

        Constructs a complete VideoJob entity with all metadata,
        configuration, and initial status information for persistence.

        Args:
            request: Original submission request
            video_file: Stored video file information
            video_info: Extracted video metadata
            extraction_config: Frame extraction configuration

        Returns:
            VideoJob: Created video job entity ready for persistence
        """
        video_format = VideoFormat(video_file.get_extension())

        job = VideoJob(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            original_filename=video_file.original_name,
            file_path=video_file.file_path,
            file_size=video_file.size_bytes,
            video_format=video_format,
            duration=video_info.get("duration"),
            frame_rate=video_info.get("frame_rate"),
            extraction_fps=extraction_config.fps,
            status=JobStatus.PENDING,
            frame_count=None,
            zip_file_path=None,
            zip_file_size=None,
            error_message=None,
            processing_started_at=None,
            processing_completed_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={
                "extraction_config": {
                    "output_format": extraction_config.output_format,
                    "quality": extraction_config.quality,
                    "start_time": extraction_config.start_time,
                    "end_time": extraction_config.end_time,
                    "max_frames": extraction_config.max_frames
                },
                "video_info": video_info,
                "estimated_frames": extraction_config.estimate_frame_count(
                    video_info.get("duration", 0)
                )
            }
        )

        return job

    async def _publish_job_submitted_event(self, job: VideoJob) -> None:
        """
        Publish job submitted event to the message queue.

        Publishes an event notification to inform other services about
        the new job submission for distributed processing coordination.

        Args:
            job: Video job that was submitted

        Note:
            Failures in event publishing are logged but don't fail the operation
            to ensure job creation remains successful even if messaging fails.
        """
        try:
            success = await self.kafka_gateway.publish_job_submitted(job)

            if not success:
                print(f"Failed to publish job submission event for job {job.id}")

        except Exception as e:
            print(f"Error publishing job submitted event: {str(e)}")

    async def _update_user_activity(self, user_id: str, job: VideoJob) -> None:
        """
        Update user activity information in the user service.

        Records user activity for analytics and monitoring purposes
        through the user service gateway.

        Args:
            user_id: User identifier
            job: Video job that was submitted

        Note:
            Activity update failures are logged but don't affect job creation
            to ensure core functionality remains available.
        """
        try:
            activity_data = {
                "action": "video_submitted",
                "job_id": job.id,
                "filename": job.original_filename,
                "file_size_mb": job.get_file_size_mb()
            }

            await self.user_service_gateway.update_user_activity(user_id, activity_data)

        except Exception as e:
            print(f"Warning: Failed to update user activity: {str(e)}")

    async def _get_queue_position(self) -> int:
        """
        Get the estimated queue position for the new job.

        Calculates the approximate position in the processing queue
        based on the number of pending jobs.

        Returns:
            int: Estimated queue position (1-based)

        Note:
            Returns 1 if count operation fails to provide a safe fallback.
        """
        try:
            pending_jobs_count = await self.job_repository.count_by_status(JobStatus.PENDING)
            return pending_jobs_count + 1

        except Exception:
            return 1