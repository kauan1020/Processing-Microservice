from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from domain.entities.video_job import VideoJob


class KafkaProducerInterface(ABC):
    """
    Service interface for Kafka message production operations.

    This interface defines the contract for publishing messages to Kafka topics
    for video processing events, job status updates, and notifications.

    The implementation should handle message serialization, partitioning,
    and delivery guarantees for reliable message processing.
    """

    @abstractmethod
    async def publish_job_submitted(self, job: VideoJob) -> bool:
        """
        Publish a message when a video job is submitted for processing.

        Args:
            job: Video job that was submitted

        Returns:
            bool: True if message was published successfully, False otherwise
        """
        pass

    @abstractmethod
    async def publish_job_started(self, job: VideoJob, worker_id: str) -> bool:
        """
        Publish a message when video processing starts.

        Args:
            job: Video job that started processing
            worker_id: ID of the worker processing the job

        Returns:
            bool: True if message was published successfully, False otherwise
        """
        pass

    @abstractmethod
    async def publish_job_completed(self, job: VideoJob) -> bool:
        """
        Publish a message when video processing completes successfully.

        Args:
            job: Video job that completed processing

        Returns:
            bool: True if message was published successfully, False otherwise
        """
        pass

    @abstractmethod
    async def publish_job_failed(self, job: VideoJob, error_message: str) -> bool:
        """
        Publish a message when video processing fails.

        Args:
            job: Video job that failed processing
            error_message: Description of the failure

        Returns:
            bool: True if message was published successfully, False otherwise
        """
        pass

    @abstractmethod
    async def publish_notification_request(self,
                                           notification_type: str,
                                           user_email: str,
                                           template_data: Dict[str, Any]) -> bool:
        """
        Publish a notification request message.

        Args:
            notification_type: Type of notification (success, failure, etc.)
            user_email: Email address to send notification to
            template_data: Data for email template rendering

        Returns:
            bool: True if message was published successfully, False otherwise
        """
        pass

    @abstractmethod
    async def publish_system_alert(self, alert_type: str, message: str,
                                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Publish system-level alerts for monitoring.

        Args:
            alert_type: Type of alert (error, warning, info)
            message: Alert message
            metadata: Optional additional alert metadata

        Returns:
            bool: True if message was published successfully, False otherwise
        """
        pass


class KafkaConsumerInterface(ABC):
    """
    Service interface for Kafka message consumption operations.

    This interface defines the contract for consuming messages from Kafka topics
    for video processing jobs and handling distributed processing workflows.

    The implementation should handle message deserialization, processing,
    and acknowledgment for reliable message consumption.
    """

    @abstractmethod
    async def consume_processing_jobs(self, handler_func, batch_size: int = 10) -> None:
        """
        Consume video processing job messages from Kafka.

        Args:
            handler_func: Async function to handle processing job messages
            batch_size: Number of messages to process in each batch
        """
        pass

    @abstractmethod
    async def consume_notification_requests(self, handler_func, batch_size: int = 50) -> None:
        """
        Consume notification request messages from Kafka.

        Args:
            handler_func: Async function to handle notification messages
            batch_size: Number of messages to process in each batch
        """
        pass

    @abstractmethod
    async def consume_system_alerts(self, handler_func, batch_size: int = 100) -> None:
        """
        Consume system alert messages from Kafka.

        Args:
            handler_func: Async function to handle alert messages
            batch_size: Number of messages to process in each batch
        """
        pass

    @abstractmethod
    async def start_consuming(self, topics: List[str]) -> None:
        """
        Start consuming messages from specified topics.

        Args:
            topics: List of Kafka topics to consume from
        """
        pass

    @abstractmethod
    async def stop_consuming(self) -> None:
        """
        Stop consuming messages and close consumer connections.
        """
        pass

    @abstractmethod
    async def commit_offset(self, topic: str, partition: int, offset: int) -> bool:
        """
        Manually commit message offset after successful processing.

        Args:
            topic: Kafka topic name
            partition: Topic partition number
            offset: Message offset to commit

        Returns:
            bool: True if commit was successful, False otherwise
        """
        pass


class KafkaTopicManagerInterface(ABC):
    """
    Service interface for Kafka topic management operations.

    This interface defines the contract for managing Kafka topics
    including creation, configuration, and monitoring operations.
    """

    @abstractmethod
    async def create_topic(self,
                           topic_name: str,
                           partitions: int = 3,
                           replication_factor: int = 2,
                           config: Optional[Dict[str, str]] = None) -> bool:
        """
        Create a new Kafka topic with specified configuration.

        Args:
            topic_name: Name of the topic to create
            partitions: Number of partitions for the topic
            replication_factor: Replication factor for the topic
            config: Optional topic configuration parameters

        Returns:
            bool: True if topic was created successfully, False otherwise
        """
        pass

    @abstractmethod
    async def delete_topic(self, topic_name: str) -> bool:
        """
        Delete a Kafka topic.

        Args:
            topic_name: Name of the topic to delete

        Returns:
            bool: True if topic was deleted successfully, False otherwise
        """
        pass

    @abstractmethod
    async def list_topics(self) -> List[str]:
        """
        List all available Kafka topics.

        Returns:
            List[str]: List of topic names
        """
        pass

    @abstractmethod
    async def get_topic_info(self, topic_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a Kafka topic.

        Args:
            topic_name: Name of the topic to get info for

        Returns:
            Optional[Dict[str, Any]]: Topic information or None if not found
        """
        pass

    @abstractmethod
    async def ensure_topics_exist(self, topics_config: Dict[str, Dict[str, Any]]) -> bool:
        """
        Ensure that required topics exist with proper configuration.

        Args:
            topics_config: Dictionary mapping topic names to their configurations

        Returns:
            bool: True if all topics exist or were created successfully
        """
        pass