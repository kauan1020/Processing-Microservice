from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload

from interfaces.repositories.processing_queue_repository_interface import ProcessingQueueRepositoryInterface
from domain.entities.processing_queue import ProcessingQueue, QueueStatus, QueuePriority
from infra.databases.models.processing_queue_model import ProcessingQueueModel


class ProcessingQueueRepository(ProcessingQueueRepositoryInterface):
    """
    PostgreSQL implementation of ProcessingQueueRepositoryInterface.

    This repository provides concrete implementation for processing queue
    data persistence using SQLAlchemy ORM with PostgreSQL database backend.

    It handles queue entity-to-model mapping, transaction management,
    and specialized queue operations including priority-based retrieval,
    worker assignment, and queue monitoring for distributed job processing.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the processing queue repository with database session.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self.session = session

    async def create(self, queue_entry: ProcessingQueue) -> ProcessingQueue:
        """
        Create a new queue entry record in the database.

        Args:
            queue_entry: ProcessingQueue entity to persist

        Returns:
            ProcessingQueue: Created entity with generated ID and timestamps
        """
        model = ProcessingQueueModel(
            job_id=queue_entry.job_id,
            user_id=queue_entry.user_id,
            priority=queue_entry.priority.value,
            status=queue_entry.status.value,
            worker_id=queue_entry.worker_id,
            retry_count=queue_entry.retry_count,
            max_retries=queue_entry.max_retries,
            scheduled_at=queue_entry.scheduled_at,
            started_at=queue_entry.started_at,
            completed_at=queue_entry.completed_at,
            error_message=queue_entry.error_message,
            processing_data=queue_entry.processing_data,
            created_at=queue_entry.created_at or datetime.utcnow(),
            updated_at=queue_entry.updated_at or datetime.utcnow()
        )

        self.session.add(model)
        await self.session.flush()

        return self._model_to_entity(model)

    async def find_by_id(self, queue_id: str) -> Optional[ProcessingQueue]:
        """
        Find a queue entry by its unique identifier.

        Args:
            queue_id: Unique identifier of the queue entry

        Returns:
            Optional[ProcessingQueue]: ProcessingQueue entity if found, None otherwise
        """
        query = select(ProcessingQueueModel).where(ProcessingQueueModel.id == queue_id)
        result = await self.session.execute(query)
        model = result.scalar_one_or_none()

        return self._model_to_entity(model) if model else None

    async def find_by_job_id(self, job_id: str) -> Optional[ProcessingQueue]:
        """
        Find a queue entry by associated job ID.

        Args:
            job_id: Video job identifier

        Returns:
            Optional[ProcessingQueue]: ProcessingQueue entity if found, None otherwise
        """
        query = select(ProcessingQueueModel).where(ProcessingQueueModel.job_id == job_id)
        result = await self.session.execute(query)
        model = result.scalar_one_or_none()

        return self._model_to_entity(model) if model else None

    async def find_next_available_jobs(self, limit: int = 10) -> List[ProcessingQueue]:
        """
        Find next available jobs ready for processing, ordered by priority and creation time.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List[ProcessingQueue]: List of queue entries ready for processing
        """
        current_time = datetime.utcnow()

        query = (
            select(ProcessingQueueModel)
            .where(
                and_(
                    or_(
                        ProcessingQueueModel.status == QueueStatus.QUEUED.value,
                        ProcessingQueueModel.status == QueueStatus.RETRY.value
                    ),
                    ProcessingQueueModel.scheduled_at <= current_time
                )
            )
            .order_by(
                ProcessingQueueModel.priority.desc(),
                ProcessingQueueModel.created_at.asc()
            )
            .limit(limit)
        )

        result = await self.session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(model) for model in models]

    async def assign_worker(self, queue_id: str, worker_id: str) -> bool:
        """
        Assign a worker to a queue entry and mark it as processing.

        Args:
            queue_id: Queue entry identifier
            worker_id: Worker identifier

        Returns:
            bool: True if assignment was successful, False otherwise
        """
        current_time = datetime.utcnow()

        query = (
            update(ProcessingQueueModel)
            .where(
                and_(
                    ProcessingQueueModel.id == queue_id,
                    or_(
                        ProcessingQueueModel.status == QueueStatus.QUEUED.value,
                        ProcessingQueueModel.status == QueueStatus.RETRY.value
                    )
                )
            )
            .values(
                worker_id=worker_id,
                status=QueueStatus.PROCESSING.value,
                started_at=current_time,
                updated_at=current_time
            )
        )

        result = await self.session.execute(query)
        return result.rowcount > 0

    async def update(self, queue_entry: ProcessingQueue) -> ProcessingQueue:
        """
        Update an existing queue entry in the database.

        Args:
            queue_entry: ProcessingQueue entity with updated information

        Returns:
            ProcessingQueue: Updated queue entry entity
        """
        queue_entry.updated_at = datetime.utcnow()

        query = (
            update(ProcessingQueueModel)
            .where(ProcessingQueueModel.id == queue_entry.id)
            .values(
                priority=queue_entry.priority.value,
                status=queue_entry.status.value,
                worker_id=queue_entry.worker_id,
                retry_count=queue_entry.retry_count,
                max_retries=queue_entry.max_retries,
                scheduled_at=queue_entry.scheduled_at,
                started_at=queue_entry.started_at,
                completed_at=queue_entry.completed_at,
                error_message=queue_entry.error_message,
                processing_data=queue_entry.processing_data,
                updated_at=queue_entry.updated_at
            )
        )

        await self.session.execute(query)
        return queue_entry

    async def delete(self, queue_id: str) -> bool:
        """
        Delete a queue entry from the database.

        Args:
            queue_id: Unique identifier of the queue entry to delete

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        query = delete(ProcessingQueueModel).where(ProcessingQueueModel.id == queue_id)
        result = await self.session.execute(query)

        return result.rowcount > 0

    async def find_by_status(self, status: QueueStatus, skip: int = 0, limit: int = 100) -> List[ProcessingQueue]:
        """
        Find queue entries by their status.

        Args:
            status: Queue status to filter by
            skip: Number of entries to skip
            limit: Maximum number of entries to return

        Returns:
            List[ProcessingQueue]: List of queue entries with the specified status
        """
        query = (
            select(ProcessingQueueModel)
            .where(ProcessingQueueModel.status == status.value)
            .order_by(ProcessingQueueModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(model) for model in models]

    async def find_stale_processing_entries(self, timeout_minutes: int = 60) -> List[ProcessingQueue]:
        """
        Find queue entries that have been processing for longer than the timeout period.

        Args:
            timeout_minutes: Maximum processing time before considering an entry stale

        Returns:
            List[ProcessingQueue]: List of entries that may be stuck in processing
        """
        timeout_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)

        query = select(ProcessingQueueModel).where(
            and_(
                ProcessingQueueModel.status == QueueStatus.PROCESSING.value,
                ProcessingQueueModel.started_at < timeout_threshold
            )
        )

        result = await self.session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(model) for model in models]

    async def count_by_status(self, status: QueueStatus) -> int:
        """
        Count the total number of queue entries with a specific status.

        Args:
            status: Queue status to count

        Returns:
            int: Total number of entries with the specified status
        """
        query = select(func.count(ProcessingQueueModel.id)).where(
            ProcessingQueueModel.status == status.value
        )
        result = await self.session.execute(query)

        return result.scalar() or 0

    async def get_queue_statistics(self) -> dict:
        """
        Get comprehensive queue statistics.

        Returns:
            dict: Dictionary containing queue statistics with performance metrics
        """
        total_query = select(func.count(ProcessingQueueModel.id))
        total_result = await self.session.execute(total_query)
        total_entries = total_result.scalar() or 0

        status_counts = {}
        for status in QueueStatus:
            count = await self.count_by_status(status)
            status_counts[status.value] = count

        avg_wait_time_query = select(
            func.avg(
                func.extract('epoch', ProcessingQueueModel.started_at - ProcessingQueueModel.created_at)
            )
        ).where(
            and_(
                ProcessingQueueModel.started_at.isnot(None),
                ProcessingQueueModel.status.in_([
                    QueueStatus.PROCESSING.value,
                    QueueStatus.COMPLETED.value
                ])
            )
        )
        avg_wait_result = await self.session.execute(avg_wait_time_query)
        avg_wait_time = avg_wait_result.scalar() or 0

        avg_processing_time_query = select(
            func.avg(
                func.extract('epoch', ProcessingQueueModel.completed_at - ProcessingQueueModel.started_at)
            )
        ).where(
            and_(
                ProcessingQueueModel.completed_at.isnot(None),
                ProcessingQueueModel.started_at.isnot(None),
                ProcessingQueueModel.status == QueueStatus.COMPLETED.value
            )
        )
        avg_processing_result = await self.session.execute(avg_processing_time_query)
        avg_processing_time = avg_processing_result.scalar() or 0

        return {
            "total_entries": total_entries,
            "queued_entries": status_counts.get(QueueStatus.QUEUED.value, 0),
            "processing_entries": status_counts.get(QueueStatus.PROCESSING.value, 0),
            "completed_entries": status_counts.get(QueueStatus.COMPLETED.value, 0),
            "failed_entries": status_counts.get(QueueStatus.FAILED.value, 0),
            "retry_entries": status_counts.get(QueueStatus.RETRY.value, 0),
            "average_wait_time": float(avg_wait_time),
            "average_processing_time": float(avg_processing_time)
        }

    async def cleanup_completed_entries(self, days_old: int = 7) -> int:
        """
        Clean up completed queue entries older than specified number of days.

        Args:
            days_old: Number of days to keep completed entries before cleanup

        Returns:
            int: Number of entries cleaned up
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        query = delete(ProcessingQueueModel).where(
            and_(
                ProcessingQueueModel.completed_at < cutoff_date,
                or_(
                    ProcessingQueueModel.status == QueueStatus.COMPLETED.value,
                    ProcessingQueueModel.status == QueueStatus.FAILED.value
                )
            )
        )

        result = await self.session.execute(query)
        return result.rowcount

    def _model_to_entity(self, model: ProcessingQueueModel) -> ProcessingQueue:
        """
        Convert SQLAlchemy model to domain entity.

        Args:
            model: ProcessingQueueModel instance from database

        Returns:
            ProcessingQueue: Domain entity with business logic
        """
        return ProcessingQueue(
            id=str(model.id),
            job_id=str(model.job_id),
            user_id=model.user_id,
            priority=QueuePriority(model.priority),
            status=QueueStatus(model.status),
            worker_id=model.worker_id,
            retry_count=model.retry_count,
            max_retries=model.max_retries,
            scheduled_at=model.scheduled_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            error_message=model.error_message,
            processing_data=model.processing_data,
            created_at=model.created_at,
            updated_at=model.updated_at
        )