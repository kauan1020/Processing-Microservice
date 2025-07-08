from typing import Optional, List, Callable
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload, sessionmaker

from interfaces.repositories.video_job_repository_interface import VideoJobRepositoryInterface
from domain.entities.video_job import VideoJob, JobStatus
from infra.databases.models.video_job_model import VideoJobModel
from domain.exceptions import VideoJobNotFoundException


class VideoJobRepository(VideoJobRepositoryInterface):
    """
    PostgreSQL implementation of VideoJobRepositoryInterface.

    This repository provides concrete implementation for video job data
    persistence using SQLAlchemy ORM with PostgreSQL database backend.

    It handles entity-to-model mapping, database transactions, query
    optimization, and error handling for all video job related operations
    while maintaining separation between domain entities and persistence.
    """

    def __init__(self, session_factory):
        """
        Initialize the video job repository with session factory.

        Args:
            session_factory: SQLAlchemy sessionmaker for creating database sessions
        """
        self.session_factory = session_factory

    async def _execute_with_session(self, operation):
        """
        Execute database operation with proper session management.

        Args:
            operation: Async function that takes a session and performs database operations

        Returns:
            Result of the operation
        """
        async with self.session_factory() as session:
            try:
                result = await operation(session)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise

    async def _execute_read_only(self, operation):
        """
        Execute read-only database operation.

        Args:
            operation: Async function that takes a session and performs read operations

        Returns:
            Result of the operation
        """
        async with self.session_factory() as session:
            return await operation(session)

    async def create(self, job: VideoJob) -> VideoJob:
        """
        Create a new video job record in the database.

        Args:
            job: VideoJob entity to persist

        Returns:
            VideoJob: Created entity with generated ID and timestamps
        """
        async def _create_operation(session: AsyncSession):
            model = VideoJobModel(
                user_id=job.user_id,
                original_filename=job.original_filename,
                file_path=job.file_path,
                file_size=job.file_size,
                video_format=job.video_format.value,
                duration=job.duration,
                frame_rate=job.frame_rate,
                extraction_fps=job.extraction_fps,
                status=job.status.value,
                frame_count=job.frame_count,
                zip_file_path=job.zip_file_path,
                zip_file_size=job.zip_file_size,
                error_message=job.error_message,
                processing_started_at=job.processing_started_at,
                processing_completed_at=job.processing_completed_at,
                created_at=job.created_at or datetime.utcnow(),
                updated_at=job.updated_at or datetime.utcnow(),
                job_metadata=job.metadata
            )

            session.add(model)
            await session.flush()
            return self._model_to_entity(model)

        return await self._execute_with_session(_create_operation)

    async def find_by_id(self, job_id: str) -> Optional[VideoJob]:
        """
        Find a video job by its unique identifier.

        Args:
            job_id: Unique identifier of the video job

        Returns:
            Optional[VideoJob]: VideoJob entity if found, None otherwise
        """
        async def _find_operation(session: AsyncSession):
            query = select(VideoJobModel).where(VideoJobModel.id == job_id)
            result = await session.execute(query)
            model = result.scalar_one_or_none()
            return self._model_to_entity(model) if model else None

        return await self._execute_read_only(_find_operation)

    async def find_by_user_id(self, user_id: str, skip: int = 0, limit: int = 100) -> List[VideoJob]:
        """
        Find video jobs belonging to a specific user with pagination.

        Args:
            user_id: User identifier
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return

        Returns:
            List[VideoJob]: List of video jobs for the user
        """
        async def _find_operation(session: AsyncSession):
            query = (
                select(VideoJobModel)
                .where(VideoJobModel.user_id == user_id)
                .order_by(VideoJobModel.created_at.desc())
                .offset(skip)
                .limit(limit)
            )

            result = await session.execute(query)
            models = result.scalars().all()
            return [self._model_to_entity(model) for model in models]

        return await self._execute_read_only(_find_operation)

    async def find_by_status(self, status: JobStatus, skip: int = 0, limit: int = 100) -> List[VideoJob]:
        """
        Find video jobs by their processing status.

        Args:
            status: Job status to filter by
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return

        Returns:
            List[VideoJob]: List of jobs with the specified status
        """
        async def _find_operation(session: AsyncSession):
            query = (
                select(VideoJobModel)
                .where(VideoJobModel.status == status.value)
                .order_by(VideoJobModel.created_at.desc())
                .offset(skip)
                .limit(limit)
            )

            result = await session.execute(query)
            models = result.scalars().all()
            return [self._model_to_entity(model) for model in models]

        return await self._execute_read_only(_find_operation)

    async def find_by_user_and_status(self, user_id: str, status: JobStatus, skip: int = 0, limit: int = 100) -> List[VideoJob]:
        """
        Find video jobs by user ID and status with pagination.

        Args:
            user_id: User identifier
            status: Job status to filter by
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return

        Returns:
            List[VideoJob]: List of jobs matching the criteria
        """
        async def _find_operation(session: AsyncSession):
            query = (
                select(VideoJobModel)
                .where(and_(VideoJobModel.user_id == user_id, VideoJobModel.status == status.value))
                .order_by(VideoJobModel.created_at.desc())
                .offset(skip)
                .limit(limit)
            )

            result = await session.execute(query)
            models = result.scalars().all()
            return [self._model_to_entity(model) for model in models]

        return await self._execute_read_only(_find_operation)

    async def count_by_user_and_status(self, user_id: str, status: JobStatus) -> int:
        """
        Count jobs by user ID and status.

        Args:
            user_id: User identifier
            status: Job status to count

        Returns:
            int: Number of jobs matching the criteria
        """
        async def _count_operation(session: AsyncSession):
            query = select(func.count(VideoJobModel.id)).where(
                and_(VideoJobModel.user_id == user_id, VideoJobModel.status == status.value)
            )
            result = await session.execute(query)
            return result.scalar() or 0

        return await self._execute_read_only(_count_operation)

    async def find_user_job_by_id(self, job_id: str, user_id: str) -> Optional[VideoJob]:
        """
        Find a video job by ID that belongs to a specific user.

        Args:
            job_id: Unique identifier of the video job
            user_id: User identifier for authorization

        Returns:
            Optional[VideoJob]: VideoJob entity if found and owned by user, None otherwise
        """
        async def _find_operation(session: AsyncSession):
            query = select(VideoJobModel).where(
                and_(VideoJobModel.id == job_id, VideoJobModel.user_id == user_id)
            )

            result = await session.execute(query)
            model = result.scalar_one_or_none()
            return self._model_to_entity(model) if model else None

        return await self._execute_read_only(_find_operation)

    async def update(self, job: VideoJob) -> VideoJob:
        """
        Update an existing video job in the database.

        Args:
            job: VideoJob entity with updated information

        Returns:
            VideoJob: Updated job entity

        Raises:
            VideoJobNotFoundException: If job doesn't exist
        """
        async def _update_operation(session: AsyncSession):
            job.updated_at = datetime.utcnow()

            query = (
                update(VideoJobModel)
                .where(VideoJobModel.id == job.id)
                .values(
                    status=job.status.value,
                    frame_count=job.frame_count,
                    zip_file_path=job.zip_file_path,
                    zip_file_size=job.zip_file_size,
                    error_message=job.error_message,
                    processing_started_at=job.processing_started_at,
                    processing_completed_at=job.processing_completed_at,
                    updated_at=job.updated_at,
                    job_metadata=job.metadata
                )
            )

            result = await session.execute(query)

            if result.rowcount == 0:
                raise VideoJobNotFoundException(job.id)

            return job

        return await self._execute_with_session(_update_operation)

    async def delete(self, job_id: str) -> bool:
        """
        Delete a video job from the database.

        Args:
            job_id: Unique identifier of the job to delete

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        async def _delete_operation(session: AsyncSession):
            query = delete(VideoJobModel).where(VideoJobModel.id == job_id)
            result = await session.execute(query)
            return result.rowcount > 0

        return await self._execute_with_session(_delete_operation)

    async def count_by_user_id(self, user_id: str) -> int:
        """
        Count the total number of jobs for a specific user.

        Args:
            user_id: User identifier

        Returns:
            int: Total number of jobs for the user
        """
        async def _count_operation(session: AsyncSession):
            query = select(func.count(VideoJobModel.id)).where(VideoJobModel.user_id == user_id)
            result = await session.execute(query)
            return result.scalar() or 0

        return await self._execute_read_only(_count_operation)

    async def count_by_status(self, status: JobStatus) -> int:
        """
        Count the total number of jobs with a specific status.

        Args:
            status: Job status to count

        Returns:
            int: Total number of jobs with the specified status
        """
        async def _count_operation(session: AsyncSession):
            query = select(func.count(VideoJobModel.id)).where(VideoJobModel.status == status.value)
            result = await session.execute(query)
            return result.scalar() or 0

        return await self._execute_read_only(_count_operation)

    async def find_pending_jobs(self, limit: int = 50) -> List[VideoJob]:
        """
        Find jobs that are pending processing, ordered by creation time.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List[VideoJob]: List of pending jobs ordered by oldest first
        """
        async def _find_operation(session: AsyncSession):
            query = (
                select(VideoJobModel)
                .where(VideoJobModel.status == JobStatus.PENDING.value)
                .order_by(VideoJobModel.created_at.asc())
                .limit(limit)
            )

            result = await session.execute(query)
            models = result.scalars().all()
            return [self._model_to_entity(model) for model in models]

        return await self._execute_read_only(_find_operation)

    async def find_stale_processing_jobs(self, timeout_minutes: int = 60) -> List[VideoJob]:
        """
        Find jobs that have been processing for longer than the timeout period.

        Args:
            timeout_minutes: Maximum processing time before considering a job stale

        Returns:
            List[VideoJob]: List of jobs that may be stuck in processing
        """
        async def _find_operation(session: AsyncSession):
            timeout_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)

            query = select(VideoJobModel).where(
                and_(
                    VideoJobModel.status == JobStatus.PROCESSING.value,
                    VideoJobModel.processing_started_at < timeout_threshold
                )
            )

            result = await session.execute(query)
            models = result.scalars().all()
            return [self._model_to_entity(model) for model in models]

        return await self._execute_read_only(_find_operation)

    async def find_jobs_by_date_range(self,
                                      start_date: datetime,
                                      end_date: datetime,
                                      user_id: Optional[str] = None) -> List[VideoJob]:
        """
        Find jobs created within a specific date range.

        Args:
            start_date: Start of the date range
            end_date: End of the date range
            user_id: Optional user ID to filter by specific user

        Returns:
            List[VideoJob]: List of jobs created within the date range
        """
        async def _find_operation(session: AsyncSession):
            conditions = [
                VideoJobModel.created_at >= start_date,
                VideoJobModel.created_at <= end_date
            ]

            if user_id:
                conditions.append(VideoJobModel.user_id == user_id)

            query = (
                select(VideoJobModel)
                .where(and_(*conditions))
                .order_by(VideoJobModel.created_at.desc())
            )

            result = await session.execute(query)
            models = result.scalars().all()
            return [self._model_to_entity(model) for model in models]

        return await self._execute_read_only(_find_operation)

    async def get_user_job_statistics(self, user_id: str) -> dict:
        """
        Get job statistics for a specific user.

        Args:
            user_id: User identifier

        Returns:
            dict: Dictionary containing job statistics
        """
        async def _stats_operation(session: AsyncSession):
            total_jobs_query = select(func.count(VideoJobModel.id)).where(VideoJobModel.user_id == user_id)
            total_jobs_result = await session.execute(total_jobs_query)
            total_jobs = total_jobs_result.scalar() or 0

            completed_jobs_query = select(func.count(VideoJobModel.id)).where(
                and_(VideoJobModel.user_id == user_id, VideoJobModel.status == JobStatus.COMPLETED.value)
            )
            completed_jobs_result = await session.execute(completed_jobs_query)
            completed_jobs = completed_jobs_result.scalar() or 0

            failed_jobs_query = select(func.count(VideoJobModel.id)).where(
                and_(VideoJobModel.user_id == user_id, VideoJobModel.status == JobStatus.FAILED.value)
            )
            failed_jobs_result = await session.execute(failed_jobs_query)
            failed_jobs = failed_jobs_result.scalar() or 0

            pending_jobs_query = select(func.count(VideoJobModel.id)).where(
                and_(VideoJobModel.user_id == user_id, VideoJobModel.status == JobStatus.PENDING.value)
            )
            pending_jobs_result = await session.execute(pending_jobs_query)
            pending_jobs = pending_jobs_result.scalar() or 0

            processing_jobs_query = select(func.count(VideoJobModel.id)).where(
                and_(VideoJobModel.user_id == user_id, VideoJobModel.status == JobStatus.PROCESSING.value)
            )
            processing_jobs_result = await session.execute(processing_jobs_query)
            processing_jobs = processing_jobs_result.scalar() or 0

            frames_query = select(func.sum(VideoJobModel.frame_count)).where(
                and_(VideoJobModel.user_id == user_id, VideoJobModel.frame_count.isnot(None))
            )
            frames_result = await session.execute(frames_query)
            total_frames = frames_result.scalar() or 0

            processing_time_query = select(
                func.sum(
                    func.extract('epoch', VideoJobModel.processing_completed_at - VideoJobModel.processing_started_at)
                )
            ).where(
                and_(
                    VideoJobModel.user_id == user_id,
                    VideoJobModel.processing_started_at.isnot(None),
                    VideoJobModel.processing_completed_at.isnot(None)
                )
            )
            processing_time_result = await session.execute(processing_time_query)
            total_processing_time = processing_time_result.scalar() or 0

            return {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "pending_jobs": pending_jobs,
                "processing_jobs": processing_jobs,
                "total_frames_extracted": int(total_frames),
                "total_processing_time": float(total_processing_time)
            }

        return await self._execute_read_only(_stats_operation)

    async def cleanup_old_jobs(self, days_old: int = 30) -> int:
        """
        Clean up jobs older than specified number of days.

        Args:
            days_old: Number of days to keep jobs before cleanup

        Returns:
            int: Number of jobs cleaned up
        """
        async def _cleanup_operation(session: AsyncSession):
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            query = delete(VideoJobModel).where(
                and_(
                    VideoJobModel.created_at < cutoff_date,
                    or_(
                        VideoJobModel.status == JobStatus.COMPLETED.value,
                        VideoJobModel.status == JobStatus.FAILED.value
                    )
                )
            )

            result = await session.execute(query)
            return result.rowcount

        return await self._execute_with_session(_cleanup_operation)

    def _model_to_entity(self, model: VideoJobModel) -> VideoJob:
        """
        Convert SQLAlchemy model to domain entity.

        Args:
            model: VideoJobModel instance from database

        Returns:
            VideoJob: Domain entity with business logic
        """
        from domain.entities.video_job import VideoFormat

        return VideoJob(
            id=str(model.id),
            user_id=model.user_id,
            original_filename=model.original_filename,
            file_path=model.file_path,
            file_size=model.file_size,
            video_format=VideoFormat(model.video_format),
            duration=model.duration,
            frame_rate=model.frame_rate,
            extraction_fps=model.extraction_fps,
            status=JobStatus(model.status),
            frame_count=model.frame_count,
            zip_file_path=model.zip_file_path,
            zip_file_size=model.zip_file_size,
            error_message=model.error_message,
            processing_started_at=model.processing_started_at,
            processing_completed_at=model.processing_completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            metadata=model.job_metadata
        )