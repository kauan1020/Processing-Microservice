from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from domain.entities.video_job import VideoJob


class KafkaGatewayInterface(ABC):
    """
    Gateway interface for Kafka message broker operations.

    This interface defines the contract for Kafka integration including
    message publishing, consumption, and topic management for distributed
    video processing workflows and event-driven architecture.

    The implementation should handle message serialization, delivery guarantees,
    consumer group management, and error handling for reliable distributed
    processing across multiple worker instances and microservices.
    """

    @abstractmethod
    async def publish_job_submitted(self, job: VideoJob, partition_key: Optional[str] = None) -> bool:
        """
        Publish a message when a video processing job is submitted to the system.

        This method sends a job submission event to the processing topic
        to notify worker services that a new video is ready for frame extraction
        processing with proper message ordering and delivery guarantees.

        Args:
            job: VideoJob entity containing complete job information and metadata
            partition_key: Optional key for message partitioning to ensure ordered processing

        Returns:
            bool: True if message was successfully published to the topic,
                 False if publishing failed due to broker connectivity or serialization issues
        """
        pass

    @abstractmethod
    async def publish_job_started(self, job: VideoJob, worker_id: str) -> bool:
        """
        Publish a message when video processing starts on a worker.

        This method publishes job start events for monitoring, load balancing,
        and progress tracking across the distributed processing system
        with worker identification for debugging and performance analysis.

        Args:
            job: VideoJob entity that has started processing
            worker_id: Unique identifier of the worker instance processing the job

        Returns:
            bool: True if message was successfully published for monitoring systems,
                 False if publishing failed but processing can continue
        """
        pass

    @abstractmethod
    async def publish_job_completed(self, job: VideoJob, processing_metrics: Dict[str, Any]) -> bool:
        """
        Publish a message when video processing completes successfully.

        This method sends completion events with processing metrics
        for analytics, billing, user notifications, and system monitoring
        to trigger downstream processes and user communications.

        Args:
            job: VideoJob entity that completed processing successfully
            processing_metrics: Dictionary containing processing statistics and performance data

        Returns:
            bool: True if completion message was published successfully,
                 False if publishing failed but job completion is still valid
        """
        pass

    @abstractmethod
    async def publish_job_failed(self, job: VideoJob, error_message: str, retry_count: int = 0) -> bool:
        """
        Publish a message when video processing fails with error details.

        This method publishes failure events with comprehensive error information
        for alerting, retry logic, user notifications, and system health monitoring
        to enable rapid response to processing issues and system failures.

        Args:
            job: VideoJob entity that failed during processing
            error_message: Detailed error description for debugging and user communication
            retry_count: Number of retry attempts made before final failure

        Returns:
            bool: True if failure message was published for alerting systems,
                 False if publishing failed but failure handling continues
        """
        pass

    @abstractmethod
    async def publish_notification_request(self,
                                           notification_type: str,
                                           user_email: str,
                                           template_data: Dict[str, Any],
                                           priority: str = "normal") -> bool:
        """
        Publish a notification request message for user communication.

        This method sends notification requests to the notification service
        (AWS Lambda or email service) with template data for personalized
        user communications about job status, completion, and system updates.

        Args:
            notification_type: Type of notification (success, failure, progress, system)
            user_email: Email address where notification should be sent
            template_data: Dictionary containing data for email template rendering
            priority: Message priority level (low, normal, high, urgent)

        Returns:
            bool: True if notification request was queued successfully,
                 False if queuing failed but core processing continues
        """
        pass

    @abstractmethod
    async def consume_processing_jobs(self,
                                      handler_func: Callable[[Dict[str, Any]], bool],
                                      consumer_group: str,
                                      max_batch_size: int = 10) -> None:
        """
        Consume video processing job messages from Kafka with batch processing.

        This method continuously polls for new job messages and processes
        them using the provided handler function with proper error handling,
        offset management, and graceful shutdown capabilities for worker services.

        Args:
            handler_func: Async function to process job messages, returns True for success
            consumer_group: Consumer group ID for distributed processing coordination
            max_batch_size: Maximum number of messages to process in each batch
        """
        pass

    @abstractmethod
    async def consume_notifications(self,
                                    handler_func: Callable[[Dict[str, Any]], bool],
                                    consumer_group: str,
                                    max_batch_size: int = 50) -> None:
        """
        Consume notification request messages for user communication processing.

        This method processes notification requests from various services
        and triggers appropriate communication channels with rate limiting
        and error handling for reliable user notification delivery.

        Args:
            handler_func: Async function to process notification messages
            consumer_group: Consumer group ID for notification service coordination
            max_batch_size: Maximum notifications to process in each batch
        """
        pass

    @abstractmethod
    async def start_consuming(self, topics: List[str], consumer_group: str) -> None:
        """
        Start consuming messages from specified topics with proper configuration.

        This method initializes Kafka consumers with appropriate settings
        for reliable message processing, automatic offset management,
        and graceful error handling for distributed processing workloads.

        Args:
            topics: List of Kafka topic names to consume messages from
            consumer_group: Consumer group identifier for distributed coordination
        """
        pass

    @abstractmethod
    async def stop_consuming(self) -> None:
        """
        Stop consuming messages and close consumer connections gracefully.

        This method performs clean shutdown of Kafka consumers with
        proper offset commits, connection cleanup, and resource disposal
        to ensure no message loss during service shutdown or restart.
        """
        pass

    @abstractmethod
    async def commit_offset(self, topic: str, partition: int, offset: int) -> bool:
        """
        Manually commit message offset after successful processing.

        This method provides fine-grained control over offset management
        for at-least-once processing guarantees and recovery from failures
        without message loss or duplicate processing in worker services.

        Args:
            topic: Kafka topic name where the message was consumed
            partition: Topic partition number for the processed message
            offset: Message offset to commit as successfully processed

        Returns:
            bool: True if offset was committed successfully to Kafka,
                 False if commit failed due to connectivity or coordination issues
        """
        pass

    @abstractmethod
    async def create_topics(self, topics_config: Dict[str, Dict[str, Any]]) -> bool:
        """
        Create required Kafka topics with appropriate configuration.

        This method ensures all necessary topics exist with proper
        partitioning, replication, and retention settings for optimal
        performance and reliability in the video processing system.

        Args:
            topics_config: Dictionary mapping topic names to configuration parameters
                          including partitions, replication factor, and retention settings

        Returns:
            bool: True if all topics were created or already exist with correct config,
                 False if topic creation failed due to permissions or broker issues
        """
        pass

    @abstractmethod
    async def get_consumer_lag(self, consumer_group: str, topic: str) -> Dict[str, Any]:
        """
        Get consumer lag metrics for monitoring and scaling decisions.

        This method retrieves consumer lag information to monitor
        processing performance and make informed decisions about
        worker scaling and resource allocation for optimal throughput.

        Args:
            consumer_group: Consumer group to check lag for
            topic: Topic name to measure lag on

        Returns:
            Dict[str, Any]: Consumer lag metrics including:
                - total_lag: Total number of unprocessed messages
                - partition_lags: Per-partition lag information
                - last_commit_time: Timestamp of last offset commit
                - estimated_processing_time: Estimated time to clear lag
        """
        pass