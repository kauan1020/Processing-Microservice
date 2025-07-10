from typing import Dict, Any
from fastapi import UploadFile, HTTPException, status

from use_cases.video_processing.submit_video_use_case import (
    SubmitVideoProcessingUseCase,
    SubmitVideoRequest,
    SubmitVideoResponse
)
from use_cases.video_processing.get_job_status_use_case import (
    GetJobStatusUseCase,
    GetJobStatusRequest,
    GetJobStatusResponse,
    ListUserJobsUseCase,
    ListUserJobsRequest,
    ListUserJobsResponse
)
from use_cases.video_processing.download_result_use_case import (
    DownloadProcessingResultUseCase,
    DownloadResultRequest,
    DownloadResultResponse,
    DeleteVideoJobUseCase,
    DeleteJobRequest,
    DeleteJobResponse
)
from interfaces.presenters.video_processing_presenter_interface import VideoProcessingPresenterInterface
from domain.exceptions import (
    ProcessingException,
    InvalidVideoFormatException,
    VideoJobNotFoundException,
    AuthorizationException,
    InvalidJobStatusException,
    StorageException
)


class VideoProcessingController:
    """
    Controller for handling video processing HTTP requests.

    This controller orchestrates the interaction between HTTP requests,
    use cases, and response presentation following Clean Architecture principles.

    It handles request validation, use case execution, error handling,
    and response formatting through presenters.
    """

    def __init__(self,
                 submit_video_use_case: SubmitVideoProcessingUseCase,
                 get_job_status_use_case: GetJobStatusUseCase,
                 list_user_jobs_use_case: ListUserJobsUseCase,
                 download_result_use_case: DownloadProcessingResultUseCase,
                 delete_job_use_case: DeleteVideoJobUseCase,
                 presenter: VideoProcessingPresenterInterface):
        """
        Initialize the video processing controller.

        Args:
            submit_video_use_case: Use case for video submission
            get_job_status_use_case: Use case for job status retrieval
            list_user_jobs_use_case: Use case for listing user jobs
            download_result_use_case: Use case for downloading results
            delete_job_use_case: Use case for job deletion
            presenter: Presenter for formatting responses
        """
        self.submit_video_use_case = submit_video_use_case
        self.get_job_status_use_case = get_job_status_use_case
        self.list_user_jobs_use_case = list_user_jobs_use_case
        self.download_result_use_case = download_result_use_case
        self.delete_job_use_case = delete_job_use_case
        self.presenter = presenter

    async def submit_video_for_processing(self,
                                          file: UploadFile,
                                          user_id: str,
                                          extraction_fps: float = 1.0,
                                          output_format: str = 'png',
                                          quality: int = 95,
                                          start_time: float = 0.0,
                                          end_time: float = None,
                                          max_frames: int = None,
                                          user_preferences: dict = None) -> Dict[
        str, Any]:  # ← ADICIONAR ESTE PARÂMETRO
        """
        Handle video submission for frame extraction processing.

        Args:
            file: Uploaded video file
            user_id: ID of the user submitting the video
            extraction_fps: Frames per second for extraction
            output_format: Output image format
            quality: Output image quality
            start_time: Start time for extraction
            end_time: End time for extraction
            max_frames: Maximum frames to extract
            user_preferences: User preferences for processing  # ← ADICIONAR ESTA DOCUMENTAÇÃO

        Returns:
            Dict[str, Any]: Formatted response with job information

        Raises:
            HTTPException: For various error conditions
        """
        try:
            self._validate_video_file(file)

            file_content = await file.read()

            # Aplicar user_preferences se disponível
            if user_preferences:
                processing_prefs = user_preferences.get("processing", {})
                # Usar preferências do usuário como padrão se não especificado
                if extraction_fps == 1.0:  # valor padrão
                    extraction_fps = processing_prefs.get("default_fps", extraction_fps)
                if quality == 95:  # valor padrão
                    quality = processing_prefs.get("default_quality", quality)
                if max_frames is None:
                    max_frames = processing_prefs.get("max_frames", max_frames)

            request = SubmitVideoRequest(
                user_id=user_id,
                file_content=file_content,
                original_filename=file.filename,
                extraction_fps=extraction_fps,
                output_format=output_format,
                quality=quality,
                start_time=start_time,
                end_time=end_time,
                max_frames=max_frames
            )

            response = await self.submit_video_use_case.execute(request)

            return self.presenter.present_video_submission_success(response)

        except InvalidVideoFormatException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=self.presenter.present_invalid_video_format_error(str(e))
            )
        except StorageException as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=self.presenter.present_storage_error(str(e))
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=self.presenter.present_validation_error(str(e))
            )
        except ProcessingException as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=self.presenter.present_processing_error(str(e))
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=self.presenter.present_internal_server_error(str(e))
            )

    async def get_job_status(self, job_id: str, user_id: str) -> Dict[str, Any]:
        """
        Handle job status retrieval requests.

        Args:
            job_id: ID of the job to get status for
            user_id: ID of the requesting user

        Returns:
            Dict[str, Any]: Formatted response with job status

        Raises:
            HTTPException: For various error conditions
        """
        try:
            request = GetJobStatusRequest(job_id=job_id, user_id=user_id)

            response = await self.get_job_status_use_case.execute(request)

            return self.presenter.present_job_status(response)

        except VideoJobNotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=self.presenter.present_job_not_found_error(str(e))
            )
        except AuthorizationException as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=self.presenter.present_authorization_error(str(e))
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=self.presenter.present_internal_server_error(str(e))
            )

    async def list_user_jobs(self,
                             user_id: str,
                             status_filter: str = None,
                             skip: int = 0,
                             limit: int = 20) -> Dict[str, Any]:
        """
        Handle user jobs listing requests.

        Args:
            user_id: ID of the user whose jobs to list
            status_filter: Optional status filter
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return

        Returns:
            Dict[str, Any]: Formatted response with job list

        Raises:
            HTTPException: For various error conditions
        """
        try:
            from domain.entities.video_job import JobStatus

            status_enum = None
            if status_filter:
                try:
                    if isinstance(status_filter, JobStatus):
                        status_enum = status_filter
                    else:
                        status_enum = JobStatus(status_filter.lower())
                except ValueError:
                    return self.presenter.present_validation_error(f"Invalid status filter: {status_filter}")

            request = ListUserJobsRequest(
                user_id=user_id,
                status_filter=status_enum,
                skip=skip,
                limit=limit
            )

            response = await self.list_user_jobs_use_case.execute(request)

            return self.presenter.present_user_jobs_list(response)

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error in list_user_jobs: {type(e).__name__}: {str(e)}")
            return self.presenter.present_internal_server_error(str(e))

    async def download_processing_result(self, job_id: str, user_id: str, include_metadata: bool = False) -> Dict[
        str, Any]:
        """
        Handle processing result download requests.

        Args:
            job_id: ID of the job to download results for
            user_id: ID of the requesting user
            include_metadata: Whether to include processing metadata

        Returns:
            Dict[str, Any]: Download information for file streaming

        Raises:
            HTTPException: For various error conditions
        """
        try:
            request = DownloadResultRequest(
                job_id=job_id,
                user_id=user_id,
                include_metadata=include_metadata
            )

            response = await self.download_result_use_case.execute(request)

            return self.presenter.present_download_info(response)

        except VideoJobNotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=self.presenter.present_job_not_found_error(str(e))
            )
        except AuthorizationException as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=self.presenter.present_authorization_error(str(e))
            )
        except InvalidJobStatusException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=self.presenter.present_invalid_job_status_error(str(e))
            )
        except StorageException as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=self.presenter.present_storage_error(str(e))
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=self.presenter.present_internal_server_error(str(e))
            )

    async def delete_video_job(self, job_id: str, user_id: str, delete_files: bool = True) -> Dict[str, Any]:
        """
        Handle video job deletion requests.

        Args:
            job_id: ID of the job to delete
            user_id: ID of the requesting user
            delete_files: Whether to delete associated files

        Returns:
            Dict[str, Any]: Formatted deletion confirmation

        Raises:
            HTTPException: For various error conditions
        """
        try:
            request = DeleteJobRequest(
                job_id=job_id,
                user_id=user_id,
                delete_files=delete_files
            )

            response = await self.delete_job_use_case.execute(request)

            return self.presenter.present_job_deletion_success(response)

        except VideoJobNotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=self.presenter.present_job_not_found_error(str(e))
            )
        except AuthorizationException as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=self.presenter.present_authorization_error(str(e))
            )
        except InvalidJobStatusException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=self.presenter.present_invalid_job_status_error(str(e))
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=self.presenter.present_internal_server_error(str(e))
            )

    def _validate_video_file(self, file: UploadFile) -> None:
        """
        Validate uploaded video file basic properties.

        Args:
            file: Uploaded file to validate

        Raises:
            ValueError: If file validation fails
        """
        if not file.filename:
            raise ValueError("Filename is required")

        if file.size and file.size > 500 * 1024 * 1024:  # 500MB
            raise ValueError("File size exceeds maximum limit of 500MB")

        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.wmv', '.flv'}
        file_extension = file.filename.lower().split('.')[-1] if '.' in file.filename else ''

        if f'.{file_extension}' not in allowed_extensions:
            raise ValueError(f"Unsupported file format: {file_extension}")

        if not file.content_type or not file.content_type.startswith('video/'):
            raise ValueError("File must be a video file")