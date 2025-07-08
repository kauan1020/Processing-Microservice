import asyncio
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logging.getLogger('asyncio').setLevel(logging.ERROR)

from interfaces.gateways.kafka_gateway_interface import KafkaGatewayInterface
from interfaces.repositories.video_job_repository_interface import VideoJobRepositoryInterface
from interfaces.services.video_processor_interface import VideoProcessorInterface
from interfaces.services.file_storage_interface import FileStorageInterface
from interfaces.gateways.notification_gateway_interface import NotificationGatewayInterface
from infra.gateways.user_service_gateway import UserServiceGateway

from use_cases.video_processing.process_video_use_case import (
    ProcessVideoUseCase,
    ProcessVideoRequest
)
from domain.exceptions import ProcessingException
from domain.entities.video_job import JobStatus


class VideoProcessingWorker:
    """
    Enhanced worker service for processing video frame extraction jobs with robust connection management.

    This worker service processes video jobs from Kafka queue or database polling with advanced
    fallback mechanisms, connection recovery, health monitoring, and comprehensive error handling
    for reliable video processing at scale with automatic recovery from network interruptions.
    """

    def __init__(self,
                 job_repository: VideoJobRepositoryInterface,
                 video_processor: VideoProcessorInterface,
                 file_storage: FileStorageInterface,
                 kafka_gateway: Optional[KafkaGatewayInterface],
                 notification_gateway: NotificationGatewayInterface,
                 user_service_gateway: UserServiceGateway,
                 worker_id: Optional[str] = None,
                 max_concurrent_jobs: int = 2,
                 health_check_interval: int = 30,
                 poll_interval: int = 5,
                 kafka_retry_interval: int = 60):
        """
        Initialize the enhanced video processing worker with required dependencies.

        Args:
            job_repository: Repository for video job data persistence operations
            video_processor: Service for video processing and frame extraction
            file_storage: Service for file storage and management operations
            kafka_gateway: Optional gateway for Kafka message operations
            notification_gateway: Gateway for sending user notifications
            user_service_gateway: Gateway for user service integration
            worker_id: Optional unique identifier for this worker instance
            max_concurrent_jobs: Maximum number of jobs to process simultaneously
            health_check_interval: Interval in seconds between health checks
            poll_interval: Interval in seconds between database polls
            kafka_retry_interval: Interval in seconds for Kafka recovery attempts
        """
        self.job_repository = job_repository
        self.video_processor = video_processor
        self.file_storage = file_storage
        self.kafka_gateway = kafka_gateway
        self.notification_gateway = notification_gateway
        self.user_service_gateway = user_service_gateway
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.max_concurrent_jobs = max_concurrent_jobs
        self.health_check_interval = health_check_interval
        self.poll_interval = poll_interval
        self.kafka_retry_interval = kafka_retry_interval

        self.process_video_use_case = ProcessVideoUseCase(
            job_repository=self.job_repository,
            video_processor=self.video_processor,
            file_storage=self.file_storage,
            notification_gateway=self.notification_gateway,
            user_service_gateway=self.user_service_gateway
        )

        self.active_jobs = {}
        self.is_running = False
        self.shutdown_requested = False
        self.last_health_check = datetime.utcnow()
        self.processed_jobs_count = 0
        self.failed_jobs_count = 0
        self.kafka_available = False
        self.polling_mode = False
        self.last_kafka_test = None
        self.kafka_failures = 0
        self.max_kafka_failures = 3

        self.main_task = None
        self.health_monitor_task = None
        self.kafka_recovery_task = None

    async def start(self) -> None:
        """
        Start the enhanced worker service and begin processing jobs with connection monitoring.

        This method initializes the worker and starts job processing using either Kafka consumer
        or database polling based on availability, with continuous connection health monitoring
        and automatic recovery mechanisms for maximum reliability.
        """
        try:
            self.is_running = True
            self.shutdown_requested = False

            print(f"Starting enhanced video processing worker: {self.worker_id}")
            print(f"Max concurrent jobs: {self.max_concurrent_jobs}")
            print(f"Kafka retry interval: {self.kafka_retry_interval}s")

            await self._test_kafka_availability()

            self.health_monitor_task = asyncio.create_task(self._health_monitor_loop())

            if not self.kafka_available or not self.kafka_gateway:
                self.kafka_recovery_task = asyncio.create_task(self._kafka_recovery_loop())

            if self.kafka_available and self.kafka_gateway:
                print(f"Worker {self.worker_id} starting in enhanced Kafka mode")
                self.main_task = asyncio.create_task(self._run_enhanced_kafka_mode())
            else:
                print(f"Worker {self.worker_id} starting in enhanced polling mode")
                self.polling_mode = True
                self.main_task = asyncio.create_task(self._run_enhanced_polling_mode())

            await self.main_task

        except Exception as e:
            print(f"Error starting enhanced worker {self.worker_id}: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"Enhanced worker {self.worker_id} start method completed")

    async def _test_kafka_availability(self) -> None:
        """
        Test Kafka availability with enhanced connection validation and failure tracking.
        """
        if not self.kafka_gateway:
            print("No Kafka gateway provided, using enhanced polling mode")
            self.kafka_available = False
            return

        try:
            print("Testing Kafka availability with enhanced validation...")
            self.last_kafka_test = datetime.utcnow()

            health = await asyncio.wait_for(self.kafka_gateway.health_check(), timeout=10)

            if health.get('healthy', False):
                self.kafka_available = True
                self.kafka_failures = 0
                print("Kafka is available and healthy - using Kafka mode")
            else:
                self.kafka_failures += 1
                print(
                    f"Kafka health check failed (failure #{self.kafka_failures}): {health.get('error', 'Unknown error')}")

                if self.kafka_failures >= self.max_kafka_failures:
                    print(f"Max Kafka failures ({self.max_kafka_failures}) reached, switching to polling mode")
                    self.kafka_available = False
                else:
                    print("Temporary Kafka issue, will retry")
                    self.kafka_available = False

        except asyncio.TimeoutError:
            self.kafka_failures += 1
            print(f"Kafka health check timed out (failure #{self.kafka_failures}), using polling mode")
            self.kafka_available = False
        except Exception as e:
            self.kafka_failures += 1
            print(f"Kafka availability test failed (failure #{self.kafka_failures}): {str(e)}")
            self.kafka_available = False

    async def _kafka_recovery_loop(self) -> None:
        """
        Background task for monitoring and recovering Kafka connectivity.
        """
        print(f"Starting Kafka recovery monitoring for worker {self.worker_id}")

        while self.is_running and not self.shutdown_requested:
            try:
                await asyncio.sleep(self.kafka_retry_interval)

                if self.shutdown_requested:
                    break

                if not self.kafka_available and self.kafka_gateway:
                    print(f"Worker {self.worker_id} attempting Kafka recovery...")

                    old_kafka_available = self.kafka_available
                    await self._test_kafka_availability()

                    if self.kafka_available and not old_kafka_available and self.polling_mode:
                        print(f"Worker {self.worker_id} Kafka recovered! Switching from polling to Kafka mode")
                        await self._switch_to_kafka_mode()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in Kafka recovery loop: {str(e)}")
                await asyncio.sleep(30)

    async def _switch_to_kafka_mode(self) -> None:
        """
        Switch from polling mode to Kafka mode when connection recovers.
        """
        try:
            if self.main_task and not self.main_task.done():
                print(f"Worker {self.worker_id} stopping polling mode to switch to Kafka")
                self.main_task.cancel()
                try:
                    await asyncio.wait_for(self.main_task, timeout=10)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

            self.polling_mode = False
            print(f"Worker {self.worker_id} starting Kafka mode after recovery")
            self.main_task = asyncio.create_task(self._run_enhanced_kafka_mode())

        except Exception as e:
            print(f"Error switching to Kafka mode: {str(e)}")

    async def _run_enhanced_kafka_mode(self) -> None:
        """
        Run worker in enhanced Kafka consumer mode with connection monitoring and recovery.
        """
        kafka_errors = 0
        max_kafka_errors = 5

        while self.is_running and not self.shutdown_requested:
            try:
                if not self.kafka_gateway:
                    raise Exception("Kafka gateway not available")

                print(f"Worker {self.worker_id} starting enhanced Kafka consumer...")

                await self.kafka_gateway.consume_processing_jobs(
                    handler_func=self._handle_job_message,
                    consumer_group="video-processing-workers",
                    max_batch_size=self.max_concurrent_jobs
                )

                kafka_errors = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                kafka_errors += 1
                print(f"Enhanced Kafka mode error #{kafka_errors}: {str(e)}")

                if kafka_errors >= max_kafka_errors:
                    print(f"Too many Kafka errors ({kafka_errors}), switching to polling mode...")
                    self.kafka_available = False
                    self.polling_mode = True
                    await self._run_enhanced_polling_mode()
                    break
                else:
                    backoff_time = min(kafka_errors * 5, 30)
                    print(f"Kafka error recovery: waiting {backoff_time}s before retry")
                    await asyncio.sleep(backoff_time)

    async def _run_enhanced_polling_mode(self) -> None:
        """
        Run worker in enhanced database polling mode with optimized scheduling.
        """
        print(f"Worker {self.worker_id} running in enhanced polling mode (poll interval: {self.poll_interval}s)")
        consecutive_empty_polls = 0
        max_empty_polls = 12
        dynamic_poll_interval = self.poll_interval

        while self.is_running and not self.shutdown_requested:
            try:
                jobs_found = await self._poll_and_process_jobs()

                if jobs_found > 0:
                    consecutive_empty_polls = 0
                    dynamic_poll_interval = self.poll_interval
                else:
                    consecutive_empty_polls += 1
                    if consecutive_empty_polls > max_empty_polls:
                        dynamic_poll_interval = min(self.poll_interval * 2, 30)
                    else:
                        dynamic_poll_interval = self.poll_interval

                if not self.shutdown_requested:
                    await asyncio.sleep(dynamic_poll_interval)

            except Exception as e:
                print(f"Error in enhanced polling mode: {str(e)}")
                await asyncio.sleep(self.poll_interval * 2)

    async def _poll_and_process_jobs(self) -> int:
        """
        Poll database for pending jobs and start processing them with enhanced logic.

        Returns:
            int: Number of jobs found and started
        """
        try:
            if len(self.active_jobs) >= self.max_concurrent_jobs:
                await self._cleanup_completed_jobs()
                return 0

            available_slots = self.max_concurrent_jobs - len(self.active_jobs)
            pending_jobs = await self.job_repository.find_pending_jobs(limit=available_slots)

            jobs_started = 0
            for job in pending_jobs:
                if job.id not in self.active_jobs and not self.shutdown_requested:
                    print(f"Worker {self.worker_id} found pending job: {job.id}")

                    self.active_jobs[job.id] = asyncio.create_task(
                        self._process_job_async(job.id)
                    )
                    jobs_started += 1

            await self._cleanup_completed_jobs()
            return jobs_started

        except Exception as e:
            print(f"Error polling for jobs: {str(e)}")
            return 0

    async def _cleanup_completed_jobs(self) -> None:
        """
        Clean up completed job tasks from active jobs tracking.
        """
        completed_jobs = []
        for job_id, task in self.active_jobs.items():
            if task.done():
                completed_jobs.append(job_id)

        for job_id in completed_jobs:
            del self.active_jobs[job_id]

    async def stop(self) -> None:
        """
        Stop the enhanced worker service gracefully with comprehensive cleanup.

        Coordinates graceful shutdown of all worker components including Kafka consumers,
        active job processing, health monitoring, and resource cleanup with proper
        timeout handling and error recovery.
        """
        print(f"Stopping enhanced video processing worker: {self.worker_id}")

        self.shutdown_requested = True

        cleanup_tasks = []

        if self.main_task and not self.main_task.done():
            cleanup_tasks.append(self._stop_main_task())

        if self.health_monitor_task and not self.health_monitor_task.done():
            cleanup_tasks.append(self._stop_health_monitor())

        if self.kafka_recovery_task and not self.kafka_recovery_task.done():
            cleanup_tasks.append(self._stop_kafka_recovery())

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

        await self._wait_for_active_jobs_completion(timeout=30)

        try:
            if self.kafka_gateway and hasattr(self.kafka_gateway, 'stop_consuming'):
                await asyncio.wait_for(self.kafka_gateway.stop_consuming(), timeout=10)
        except (asyncio.TimeoutError, Exception) as e:
            print(f"Warning: Error stopping Kafka consumer: {str(e)}")

        await asyncio.sleep(0.1)
        self.is_running = False

        print(
            f"Enhanced worker {self.worker_id} stopped. Processed: {self.processed_jobs_count}, Failed: {self.failed_jobs_count}")

    async def _stop_main_task(self) -> None:
        """Stop main processing task with timeout."""
        try:
            self.main_task.cancel()
            await asyncio.wait_for(self.main_task, timeout=8)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    async def _stop_health_monitor(self) -> None:
        """Stop health monitoring task with timeout."""
        try:
            self.health_monitor_task.cancel()
            await asyncio.wait_for(self.health_monitor_task, timeout=3)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    async def _stop_kafka_recovery(self) -> None:
        """Stop Kafka recovery task with timeout."""
        try:
            self.kafka_recovery_task.cancel()
            await asyncio.wait_for(self.kafka_recovery_task, timeout=3)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    async def _handle_job_message(self, message: Dict[str, Any]) -> bool:
        """
        Handle incoming job message from Kafka with enhanced validation and processing.

        Args:
            message: Job message data from Kafka

        Returns:
            bool: True if message was processed successfully, False otherwise
        """
        try:
            if self.shutdown_requested:
                return False

            if len(self.active_jobs) >= self.max_concurrent_jobs:
                print(f"Worker {self.worker_id} at capacity ({len(self.active_jobs)}/{self.max_concurrent_jobs})")
                return False

            job_id = message.get("job_id")
            if not job_id:
                print("Invalid message: missing job_id")
                return True

            if job_id in self.active_jobs:
                print(f"Job {job_id} is already being processed")
                return True

            job = await self.job_repository.find_by_id(job_id)
            if not job:
                print(f"Job {job_id} not found in database")
                return True

            if job.status != JobStatus.PENDING:
                print(f"Job {job_id} is not in pending status: {job.status}")
                return True

            print(f"Worker {self.worker_id} received job from Kafka: {job_id}")

            self.active_jobs[job_id] = asyncio.create_task(
                self._process_job_async(job_id)
            )

            return True

        except Exception as e:
            print(f"Error handling job message: {str(e)}")
            return False

    async def _process_job_async(self, job_id: str) -> None:
        """
        Process a video job asynchronously with comprehensive error handling and monitoring.

        Args:
            job_id: Unique identifier of the job to process
        """
        processing_start_time = datetime.utcnow()

        try:
            print(f"Worker {self.worker_id} starting enhanced processing for job {job_id}")

            job = await self.job_repository.find_by_id(job_id)
            if not job:
                print(f"Job {job_id} not found during processing")
                return

            request = ProcessVideoRequest(
                job_id=job_id,
                worker_id=self.worker_id
            )

            response = await self.process_video_use_case.execute(request)
            processing_duration = (datetime.utcnow() - processing_start_time).total_seconds()

            if response.success:
                await self._handle_successful_processing(job_id, response, processing_duration)
                self.processed_jobs_count += 1
                print(f"Worker {self.worker_id} completed job {job_id} in {processing_duration:.2f}s")
            else:
                await self._handle_failed_processing(job_id, response.error_message)
                self.failed_jobs_count += 1
                print(f"Worker {self.worker_id} failed job {job_id}: {response.error_message}")

        except ProcessingException as e:
            await self._handle_processing_exception(job_id, str(e))
            self.failed_jobs_count += 1
            print(f"Worker {self.worker_id} processing exception for job {job_id}: {str(e)}")

        except Exception as e:
            await self._handle_unexpected_error(job_id, str(e))
            self.failed_jobs_count += 1
            print(f"Worker {self.worker_id} unexpected error for job {job_id}: {str(e)}")
            import traceback
            traceback.print_exc()

    async def _handle_successful_processing(self, job_id: str, response, processing_duration: float) -> None:
        """Handle successful job processing with enhanced notification."""
        try:
            job = await self.job_repository.find_by_id(job_id)
            if job and self.kafka_gateway and hasattr(self.kafka_gateway, 'publish_job_completed'):
                processing_metrics = {
                    "frame_count": response.frame_count,
                    "zip_size_bytes": response.zip_file_size,
                    "processing_duration": processing_duration,
                    "worker_id": self.worker_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await self.kafka_gateway.publish_job_completed(job, processing_metrics)
        except Exception as e:
            print(f"Error publishing job completion for {job_id}: {str(e)}")

    async def _handle_failed_processing(self, job_id: str, error_message: str) -> None:
        """Handle failed job processing with enhanced notification."""
        try:
            job = await self.job_repository.find_by_id(job_id)
            if job and self.kafka_gateway and hasattr(self.kafka_gateway, 'publish_job_failed'):
                await self.kafka_gateway.publish_job_failed(job, error_message)
        except Exception as e:
            print(f"Error publishing job failure for {job_id}: {str(e)}")

    async def _handle_processing_exception(self, job_id: str, error_message: str) -> None:
        """Handle processing exceptions with enhanced logging."""
        await self._handle_failed_processing(job_id, f"Processing exception: {error_message}")

    async def _handle_unexpected_error(self, job_id: str, error_message: str) -> None:
        """Handle unexpected system errors with enhanced logging."""
        await self._handle_failed_processing(job_id, f"Unexpected error: {error_message}")

    async def _wait_for_active_jobs_completion(self, timeout: int = 60) -> None:
        """Wait for all active jobs to complete with enhanced timeout handling."""
        if not self.active_jobs:
            return

        print(f"Waiting for {len(self.active_jobs)} active jobs to complete (timeout: {timeout}s)...")

        try:
            await asyncio.wait_for(
                asyncio.gather(*self.active_jobs.values(), return_exceptions=True),
                timeout=timeout
            )
            print("All active jobs completed successfully")
        except asyncio.TimeoutError:
            print(f"Timeout waiting for jobs completion, cancelling {len(self.active_jobs)} jobs")
            for job_id, task in self.active_jobs.items():
                if not task.done():
                    print(f"Cancelling job {job_id}")
                    task.cancel()

    async def _health_monitor_loop(self) -> None:
        """Enhanced background health monitoring loop with comprehensive metrics."""
        worker_start_time = datetime.utcnow()

        while self.is_running and not self.shutdown_requested:
            try:
                await asyncio.sleep(self.health_check_interval)

                if self.shutdown_requested:
                    break

                self.last_health_check = datetime.utcnow()
                uptime = (datetime.utcnow() - worker_start_time).total_seconds()

                health_info = {
                    "worker_id": self.worker_id,
                    "mode": "polling" if self.polling_mode else "kafka",
                    "kafka_available": self.kafka_available,
                    "kafka_failures": self.kafka_failures,
                    "active_jobs": len(self.active_jobs),
                    "processed_jobs": self.processed_jobs_count,
                    "failed_jobs": self.failed_jobs_count,
                    "uptime": uptime,
                    "success_rate": self._calculate_success_rate()
                }

                print(
                    f"Worker {self.worker_id} health [{health_info['mode']}]: "
                    f"{len(self.active_jobs)} active, {self.processed_jobs_count} processed, "
                    f"{self.failed_jobs_count} failed, {health_info['success_rate']:.1f}% success"
                )

                if self.last_kafka_test and datetime.utcnow() - self.last_kafka_test > timedelta(minutes=5):
                    if not self.kafka_available:
                        print(f"Worker {self.worker_id} retesting Kafka availability...")
                        await self._test_kafka_availability()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Health monitor error: {str(e)}")
                await asyncio.sleep(30)

    def _calculate_success_rate(self) -> float:
        """Calculate current job processing success rate."""
        total_jobs = self.processed_jobs_count + self.failed_jobs_count
        if total_jobs == 0:
            return 100.0
        return (self.processed_jobs_count / total_jobs) * 100.0

    def get_worker_status(self) -> Dict[str, Any]:
        """Get comprehensive worker status and metrics with enhanced information."""
        return {
            "worker_id": self.worker_id,
            "is_running": self.is_running,
            "shutdown_requested": self.shutdown_requested,
            "mode": "polling" if self.polling_mode else "kafka",
            "kafka_available": self.kafka_available,
            "kafka_failures": self.kafka_failures,
            "kafka_retry_interval": self.kafka_retry_interval,
            "active_jobs_count": len(self.active_jobs),
            "active_job_ids": list(self.active_jobs.keys()),
            "processed_jobs_total": self.processed_jobs_count,
            "failed_jobs_total": self.failed_jobs_count,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "last_kafka_test": self.last_kafka_test.isoformat() if self.last_kafka_test else None,
            "success_rate": self._calculate_success_rate(),
            "poll_interval": self.poll_interval,
            "health_check_interval": self.health_check_interval
        }