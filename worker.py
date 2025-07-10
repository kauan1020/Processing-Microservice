import asyncio
import signal
import sys
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from contextlib import suppress

from infra.settings.settings import get_settings
from infra.repositories.video_job_repository import VideoJobRepository
from infra.services.video_processor_service import VideoProcessorService
from infra.services.file_storage_service import FileStorageService
from infra.gateways.kafka_gateway import KafkaGateway
from infra.gateways.user_service_gateway import UserServiceGateway
from use_cases.workers.video_processing_worker import VideoProcessingWorker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


class WorkerManager:
    """
    Manager class for coordinating multiple video processing workers with robust connection management.

    This manager handles the complete lifecycle of worker processes including initialization
    of dependencies, startup coordination, health monitoring, connection recovery, and
    graceful shutdown procedures for distributed video processing operations.
    """

    def __init__(self, num_workers: int = 1, worker_id_prefix: Optional[str] = None):
        """
        Initialize the worker manager with specified worker configuration.
        """
        self.num_workers = max(1, num_workers)
        self.worker_id_prefix = worker_id_prefix or "worker"
        self.settings = get_settings()
        self.engine = None
        self.session_factory = None

        self.workers: List[VideoProcessingWorker] = []
        self.worker_tasks: List[asyncio.Task] = []
        self.is_running = False
        self.shutdown_requested = False
        self.start_time = None

        self.video_processor_service = None
        self.file_storage_service = None
        self.kafka_gateway = None
        self.notification_gateway = None
        self.user_service_gateway = None

        self.health_monitor_task = None
        self.system_monitor_task = None

        logging.getLogger('aiokafka').setLevel(logging.ERROR)
        logging.getLogger('kafka').setLevel(logging.ERROR)
        logging.getLogger('asyncio').setLevel(logging.ERROR)

    async def initialize_dependencies(self) -> None:
        """
        Initialize all required dependencies with enhanced error handling and connection management.
        """
        print("Initializing worker dependencies...")

        try:
            await self._initialize_database()
            await self._initialize_services()
            await self._initialize_gateways()

            print("All services initialized successfully")

        except Exception as e:
            print(f"Failed to initialize dependencies: {str(e)}")
            raise

    async def _initialize_database(self) -> None:
        """Initialize database connection with enhanced configuration."""
        database_url = getattr(self.settings, 'database_url', None) or self.settings.database.url
        if not database_url:
            database_url = f"postgresql+asyncpg://{self.settings.database.user}:{self.settings.database.password}@{self.settings.database.host}:{self.settings.database.port}/{self.settings.database.name}"

        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600
        )

        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        print(f"Database connection established: {self.settings.database.host}")

    async def _initialize_services(self) -> None:
        """Initialize video processing and storage services."""
        self.video_processor_service = VideoProcessorService(
            ffmpeg_path=self.settings.processing.ffmpeg_path,
            ffprobe_path=self.settings.processing.ffprobe_path,
            max_concurrent_processes=getattr(self.settings.processing, 'max_concurrent_jobs', 10)
        )

        self.file_storage_service = FileStorageService(
            base_storage_path=self.settings.storage.base_path,
            max_file_size_mb=self.settings.processing.max_file_size_mb
        )

        print("Video processing and storage services initialized")

    async def _initialize_gateways(self) -> None:
        """Initialize gateway services with enhanced configuration."""
        self.kafka_gateway = KafkaGateway(
            bootstrap_servers=self.settings.kafka.bootstrap_servers,
            security_protocol=self.settings.kafka.security_protocol
        )

        from infra.gateways.notification_gateway import NotificationGateway
        self.notification_gateway = NotificationGateway(
            gmail_email=self.settings.notification.gmail_email,
            gmail_app_password=self.settings.notification.gmail_app_password,
            from_name=self.settings.notification.from_name,
            admin_emails=self.settings.notification.get_admin_emails_list()
        )

        self.user_service_gateway = UserServiceGateway(
            user_service_url=self.settings.user_service.service_url,
            timeout=getattr(self.settings.user_service, 'timeout', 30)
        )

        print("Gateway services initialized")

    async def create_workers(self) -> None:
        """
        Create and configure worker instances with optimized settings.
        """
        print(f"Creating {self.num_workers} worker instance(s)...")

        max_concurrent_per_worker = getattr(self.settings.processing, 'max_concurrent_jobs_per_worker', 2)
        kafka_retry_interval = getattr(self.settings.kafka, 'retry_interval', 60)

        print(f"Using max_concurrent_jobs_per_worker: {max_concurrent_per_worker}")
        print(f"Using kafka_retry_interval: {kafka_retry_interval}s")

        for i in range(self.num_workers):
            worker_id = f"{self.worker_id_prefix}-{i + 1}"

            worker_repository = VideoJobRepository(self.session_factory)

            worker = VideoProcessingWorker(
                job_repository=worker_repository,
                video_processor=self.video_processor_service,
                file_storage=self.file_storage_service,
                kafka_gateway=self.kafka_gateway,
                notification_gateway=self.notification_gateway,
                user_service_gateway=self.user_service_gateway,
                worker_id=worker_id,
                max_concurrent_jobs=max_concurrent_per_worker,
                health_check_interval=30,
                poll_interval=5,
                kafka_retry_interval=kafka_retry_interval
            )

            self.workers.append(worker)
            print(f"Created worker: {worker_id} (max_concurrent: {max_concurrent_per_worker})")

    async def start_workers(self) -> None:
        """
        Start all configured worker instances with enhanced monitoring and coordination.
        """
        print("Starting worker instances...")

        await self.create_workers()

        for worker in self.workers:
            task = asyncio.create_task(worker.start())
            self.worker_tasks.append(task)
            print(f"Started worker: {worker.worker_id}")

        self._start_monitoring_tasks()

        try:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        except Exception as e:
            print(f"Error in worker tasks: {str(e)}")

    def _start_monitoring_tasks(self) -> None:
        """Start background monitoring tasks for system health and performance."""
        self.health_monitor_task = asyncio.create_task(self._system_health_monitor())
        self.system_monitor_task = asyncio.create_task(self._performance_monitor())
        print("Started monitoring tasks")

    async def run(self) -> None:
        """
        Run the worker manager with comprehensive lifecycle management.
        """
        try:
            self.is_running = True
            self.start_time = datetime.utcnow()

            await self.initialize_dependencies()
            await self.start_workers()

            print("All workers started successfully")
            print("Monitoring and recovery systems active")
            print("Press Ctrl+C to stop workers gracefully")

            while self.is_running and not self.shutdown_requested:
                await asyncio.sleep(10)

        except KeyboardInterrupt:
            print("\nShutdown signal received")
            await self.shutdown()
        except Exception as e:
            print(f"Error running workers: {str(e)}")
            import traceback
            traceback.print_exc()
            await self.cleanup()
            raise

    async def _system_health_monitor(self) -> None:
        """System health monitoring with comprehensive metrics and alerting."""
        print("Starting system health monitor")

        while self.is_running and not self.shutdown_requested:
            try:
                await asyncio.sleep(60)

                if self.shutdown_requested:
                    break

                health_summary = await self._collect_health_metrics()
                self._log_health_summary(health_summary)

                if health_summary.get('critical_issues'):
                    await self._handle_critical_issues(health_summary['critical_issues'])

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Health monitor error: {str(e)}")
                await asyncio.sleep(30)

    async def _performance_monitor(self) -> None:
        """Performance monitoring with system metrics and optimization recommendations."""
        print("Starting performance monitor")

        while self.is_running and not self.shutdown_requested:
            try:
                await asyncio.sleep(300)

                if self.shutdown_requested:
                    break

                perf_metrics = await self._collect_performance_metrics()
                self._log_performance_metrics(perf_metrics)

                optimization_suggestions = self._analyze_performance(perf_metrics)
                if optimization_suggestions:
                    self._log_optimization_suggestions(optimization_suggestions)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Performance monitor error: {str(e)}")
                await asyncio.sleep(60)

    async def _collect_health_metrics(self) -> dict:
        """Collect comprehensive health metrics from all system components."""
        health_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'uptime': (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0,
            'workers': [],
            'kafka_health': None,
            'database_health': None,
            'critical_issues': []
        }

        for worker in self.workers:
            try:
                worker_status = worker.get_worker_status()
                health_data['workers'].append(worker_status)

                if not worker_status.get('is_running'):
                    health_data['critical_issues'].append(f"Worker {worker.worker_id} is not running")

                if worker_status.get('success_rate', 100) < 50:
                    health_data['critical_issues'].append(
                        f"Worker {worker.worker_id} has low success rate: {worker_status.get('success_rate'):.1f}%")
            except Exception as e:
                health_data['critical_issues'].append(f"Failed to get status from worker {worker.worker_id}: {str(e)}")

        try:
            if self.kafka_gateway:
                kafka_health = await self.kafka_gateway.health_check()
                health_data['kafka_health'] = kafka_health
                if not kafka_health.get('healthy'):
                    health_data['critical_issues'].append(f"Kafka unhealthy: {kafka_health.get('error')}")
        except Exception as e:
            health_data['critical_issues'].append(f"Kafka health check failed: {str(e)}")

        try:
            if self.engine:
                async with self.session_factory() as session:
                    from sqlalchemy import text
                    await session.execute(text("SELECT 1"))
                    health_data['database_health'] = {'status': 'healthy'}
        except Exception as e:
            health_data['database_health'] = {'status': 'unhealthy', 'error': str(e)}
            health_data['critical_issues'].append(f"Database unhealthy: {str(e)}")

        return health_data

    async def _collect_performance_metrics(self) -> dict:
        """Collect comprehensive performance metrics for analysis and optimization."""
        perf_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_workers': len(self.workers),
            'total_processed': sum(w.processed_jobs_count for w in self.workers),
            'total_failed': sum(w.failed_jobs_count for w in self.workers),
            'active_jobs': sum(len(w.active_jobs) for w in self.workers),
            'average_success_rate': 0,
            'worker_utilization': {},
            'system_efficiency': {}
        }

        total_jobs = perf_data['total_processed'] + perf_data['total_failed']
        if total_jobs > 0:
            perf_data['average_success_rate'] = (perf_data['total_processed'] / total_jobs) * 100

        for worker in self.workers:
            status = worker.get_worker_status()
            perf_data['worker_utilization'][worker.worker_id] = {
                'active_jobs': status.get('active_jobs_count', 0),
                'max_concurrent': status.get('max_concurrent_jobs', 0),
                'utilization_percent': (status.get('active_jobs_count', 0) / status.get('max_concurrent_jobs',
                                                                                        1)) * 100,
                'success_rate': status.get('success_rate', 0),
                'mode': status.get('mode', 'unknown')
            }

        kafka_workers = sum(1 for w in self.workers if not w.polling_mode)
        polling_workers = len(self.workers) - kafka_workers

        perf_data['system_efficiency'] = {
            'kafka_workers': kafka_workers,
            'polling_workers': polling_workers,
            'kafka_availability': self.kafka_gateway is not None and any(not w.polling_mode for w in self.workers),
            'overall_utilization': (perf_data['active_jobs'] / (len(self.workers) * 2)) * 100 if self.workers else 0
        }

        return perf_data

    def _log_health_summary(self, health_data: dict) -> None:
        """Log comprehensive health summary with clear formatting."""
        print(f"\n{'=' * 60}")
        print(f"SYSTEM HEALTH REPORT - {health_data['timestamp']}")
        print(f"{'=' * 60}")
        print(f"System Uptime: {health_data['uptime']:.1f}s")
        print(
            f"Active Workers: {len([w for w in health_data['workers'] if w.get('is_running')])}/{len(health_data['workers'])}")

        if health_data['kafka_health']:
            kafka_status = "HEALTHY" if health_data['kafka_health'].get('healthy') else "UNHEALTHY"
            print(f"Kafka Status: {kafka_status}")

        if health_data['database_health']:
            db_status = "HEALTHY" if health_data['database_health'].get('status') == 'healthy' else "UNHEALTHY"
            print(f"Database Status: {db_status}")

        if health_data['critical_issues']:
            print(f"\nCRITICAL ISSUES ({len(health_data['critical_issues'])}):")
            for issue in health_data['critical_issues']:
                print(f"   - {issue}")
        else:
            print(f"\nNo critical issues detected")

        print(f"{'=' * 60}\n")

    def _log_performance_metrics(self, perf_data: dict) -> None:
        """Log comprehensive performance metrics with analysis."""
        print(f"\n{'=' * 60}")
        print(f"PERFORMANCE REPORT - {perf_data['timestamp']}")
        print(f"{'=' * 60}")
        print(f"Total Jobs Processed: {perf_data['total_processed']}")
        print(f"Total Jobs Failed: {perf_data['total_failed']}")
        print(f"Average Success Rate: {perf_data['average_success_rate']:.1f}%")
        print(f"Currently Active Jobs: {perf_data['active_jobs']}")
        print(f"Overall System Utilization: {perf_data['system_efficiency']['overall_utilization']:.1f}%")

        print(f"\nWorker Distribution:")
        print(f"  Kafka Mode: {perf_data['system_efficiency']['kafka_workers']} workers")
        print(f"  Polling Mode: {perf_data['system_efficiency']['polling_workers']} workers")

        print(f"\nWorker Utilization:")
        for worker_id, util in perf_data['worker_utilization'].items():
            print(
                f"  {worker_id}: {util['utilization_percent']:.1f}% ({util['active_jobs']}/{util['max_concurrent']}) - {util['mode']} mode - {util['success_rate']:.1f}% success")

        print(f"{'=' * 60}\n")

    def _analyze_performance(self, perf_data: dict) -> List[str]:
        """Analyze performance metrics and provide optimization suggestions."""
        suggestions = []

        if perf_data['average_success_rate'] < 80:
            suggestions.append(
                f"Low success rate ({perf_data['average_success_rate']:.1f}%) - investigate job failures")

        if perf_data['system_efficiency']['overall_utilization'] > 90:
            suggestions.append("High system utilization - consider adding more workers")
        elif perf_data['system_efficiency']['overall_utilization'] < 20:
            suggestions.append("Low system utilization - consider reducing workers or increasing job flow")

        if perf_data['system_efficiency']['polling_workers'] > perf_data['system_efficiency']['kafka_workers']:
            suggestions.append("Most workers in polling mode - check Kafka connectivity")

        underperforming_workers = []
        for worker_id, util in perf_data['worker_utilization'].items():
            if util['success_rate'] < 70:
                underperforming_workers.append(worker_id)

        if underperforming_workers:
            suggestions.append(f"Underperforming workers detected: {', '.join(underperforming_workers)}")

        return suggestions

    def _log_optimization_suggestions(self, suggestions: List[str]) -> None:
        """Log optimization suggestions with clear formatting."""
        print(f"\nOPTIMIZATION SUGGESTIONS:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"   {i}. {suggestion}")
        print()

    async def _handle_critical_issues(self, issues: List[str]) -> None:
        """Handle critical system issues with automated responses where possible."""
        print(f"\nHANDLING {len(issues)} CRITICAL ISSUES:")

        for issue in issues:
            print(f"   Processing: {issue}")

            if "Kafka unhealthy" in issue:
                await self._handle_kafka_issues()
            elif "Database unhealthy" in issue:
                await self._handle_database_issues()
            elif "Worker" in issue and "not running" in issue:
                await self._handle_worker_issues()

    async def _handle_kafka_issues(self) -> None:
        """Handle Kafka-related critical issues."""
        print("   Triggering Kafka recovery procedures for all workers")
        for worker in self.workers:
            if hasattr(worker, '_test_kafka_availability'):
                asyncio.create_task(worker._test_kafka_availability())

    async def _handle_database_issues(self) -> None:
        """Handle database-related critical issues."""
        print("   Attempting database connection recovery")
        try:
            if self.engine:
                await self.engine.dispose()
                await self._initialize_database()
                print("   Database connection recovered")
        except Exception as e:
            print(f"   Database recovery failed: {str(e)}")

    async def _handle_worker_issues(self) -> None:
        """Handle worker-related critical issues."""
        print("   Checking worker health and attempting recovery")

    async def shutdown(self) -> None:
        """
        Perform graceful shutdown with comprehensive cleanup and monitoring.
        """
        print("Initiating graceful shutdown...")

        self.shutdown_requested = True
        self.is_running = False

        shutdown_start = datetime.utcnow()

        await self._stop_monitoring_tasks()

        shutdown_tasks = []
        for worker in self.workers:
            task = asyncio.create_task(worker.stop())
            shutdown_tasks.append(task)

        if shutdown_tasks:
            try:
                print(f"Stopping {len(shutdown_tasks)} workers...")
                await asyncio.wait_for(
                    asyncio.gather(*shutdown_tasks, return_exceptions=True),
                    timeout=45
                )
                print("All workers stopped successfully")
            except asyncio.TimeoutError:
                print("Warning: Some workers did not stop within timeout")

        await self._stop_worker_tasks()
        await self.cleanup()

        shutdown_duration = (datetime.utcnow() - shutdown_start).total_seconds()
        print(f"Graceful shutdown completed in {shutdown_duration:.2f}s")

    async def _stop_monitoring_tasks(self) -> None:
        """Stop monitoring tasks with proper timeout handling."""
        monitoring_tasks = []

        if self.health_monitor_task and not self.health_monitor_task.done():
            monitoring_tasks.append(self.health_monitor_task)

        if self.system_monitor_task and not self.system_monitor_task.done():
            monitoring_tasks.append(self.system_monitor_task)

        if monitoring_tasks:
            print("Stopping monitoring tasks...")
            for task in monitoring_tasks:
                task.cancel()

            try:
                await asyncio.wait_for(
                    asyncio.gather(*monitoring_tasks, return_exceptions=True),
                    timeout=5
                )
                print("Monitoring tasks stopped")
            except asyncio.TimeoutError:
                print("Warning: Monitoring tasks stop timed out")

    async def _stop_worker_tasks(self) -> None:
        """Stop worker tasks with proper cleanup."""
        if self.worker_tasks:
            print("Stopping worker tasks...")
            for task in self.worker_tasks:
                if not task.done():
                    task.cancel()

            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.worker_tasks, return_exceptions=True),
                    timeout=10
                )
                print("Worker tasks stopped")
            except asyncio.TimeoutError:
                print("Warning: Worker tasks stop timed out")

    async def cleanup(self) -> None:
        """
        Cleanup of system resources and connections.
        """
        print("Starting resource cleanup...")

        cleanup_tasks = []

        if self.kafka_gateway:
            cleanup_tasks.append(self._cleanup_kafka_gateway())

        if self.engine:
            cleanup_tasks.append(self._cleanup_database())

        if cleanup_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=15
                )
            except asyncio.TimeoutError:
                print("Warning: Resource cleanup timed out")

        print("Resource cleanup completed")

    async def _cleanup_kafka_gateway(self) -> None:
        """Cleanup Kafka gateway with proper error handling."""
        try:
            print("Cleaning up Kafka gateway...")
            await self.kafka_gateway.stop_consuming()
            print("Kafka gateway cleaned up")
        except Exception as e:
            print(f"Warning: Kafka gateway cleanup error: {str(e)}")

    async def _cleanup_database(self) -> None:
        """Cleanup database connections with proper error handling."""
        try:
            print("Cleaning up database connections...")
            await asyncio.sleep(0.1)
            with suppress(Exception):
                await self.engine.dispose()
            print("Database connections cleaned up")
        except Exception as e:
            print(f"Warning: Database cleanup error: {str(e)}")


def setup_signal_handlers(worker_manager: WorkerManager) -> None:
    """
    Setup system signal handlers for graceful shutdown.
    """

    def signal_handler(signum, frame):
        print(f"\nReceived shutdown signal {signum}")
        asyncio.create_task(worker_manager.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("Signal handlers configured")


async def main() -> None:
    """
    Main entry point for video processing worker service.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Video Processing Worker Service")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker instances")
    parser.add_argument("--worker-id-prefix", type=str, help="Worker ID prefix")

    args = parser.parse_args()

    print("FIAP X - Video Processing Worker Service")
    print("=" * 60)
    print(f"Workers: {args.workers}")
    print(f"Worker ID Prefix: {args.worker_id_prefix or 'worker'}")

    settings = get_settings()
    print(f"Environment: {getattr(settings, 'environment', 'development')}")
    print(f"Database: {getattr(settings.database, 'host', 'localhost')}:{getattr(settings.database, 'port', 5432)}")
    print(f"Kafka: {getattr(settings.kafka, 'bootstrap_servers', 'localhost:9092')}")
    print(f"Gmail: {getattr(settings.notification, 'gmail_email', '')}")
    print(f"Features: Connection Recovery, Health Monitoring, Performance Analysis")
    print("=" * 60)

    worker_manager = WorkerManager(
        num_workers=args.workers,
        worker_id_prefix=args.worker_id_prefix
    )

    setup_signal_handlers(worker_manager)

    try:
        await worker_manager.run()
    except Exception as e:
        print(f"Fatal error in worker service: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())