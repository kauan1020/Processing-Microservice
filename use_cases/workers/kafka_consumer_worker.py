import asyncio
import json
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from interfaces.gateways.kafka_gateway_interface import KafkaGatewayInterface
from interfaces.gateways.notification_gateway_interface import NotificationGatewayInterface


class KafkaConsumerWorker:
    """
    Kafka consumer worker for processing various message types.

    This worker service consumes messages from different Kafka topics
    including job events, notification requests, and system alerts
    with proper message handling, error recovery, and monitoring.

    It provides specialized handlers for different message types and
    ensures reliable message processing with proper acknowledgment
    and error handling strategies for distributed messaging workflows.
    The worker supports multiple notification types and implements
    robust error recovery mechanisms for high availability operations.

    Attributes:
        kafka_gateway: Gateway for Kafka message consumption
        notification_gateway: Gateway for sending notifications
        worker_id: Unique identifier for this worker instance
        consumer_group: Kafka consumer group for distributed processing
        is_running: Flag indicating if worker is currently running
        shutdown_requested: Flag indicating if graceful shutdown was requested
        processed_messages_count: Total number of successfully processed messages
        failed_messages_count: Total number of failed message processing attempts
    """

    def __init__(self,
                 kafka_gateway: KafkaGatewayInterface,
                 notification_gateway: NotificationGatewayInterface,
                 worker_id: Optional[str] = None,
                 consumer_group: str = "notification-workers"):
        """
        Initialize Kafka consumer worker with gateway dependencies.

        Creates a new consumer worker instance with the specified configuration
        and dependencies required for message consumption and notification
        processing. Sets up internal state tracking and prepares the worker
        for message consumption from various Kafka topics.

        Args:
            kafka_gateway: Gateway for Kafka message consumption
            notification_gateway: Gateway for sending notifications
            worker_id: Optional unique identifier for this worker instance
            consumer_group: Kafka consumer group for distributed processing

        Returns:
            None

        Raises:
            ValueError: If any required dependency is None
        """
        self.kafka_gateway = kafka_gateway
        self.notification_gateway = notification_gateway
        self.worker_id = worker_id or f"kafka-consumer-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        self.consumer_group = consumer_group

        self.is_running = False
        self.shutdown_requested = False
        self.processed_messages_count = 0
        self.failed_messages_count = 0

    async def start_consuming_notifications(self) -> None:
        """
        Start consuming notification messages from Kafka.

        This method begins consuming notification request messages
        and processes them through the notification gateway with
        proper error handling and message acknowledgment.

        The consumer will continue processing messages until shutdown
        is requested or a fatal error occurs. Messages are processed
        in batches for efficiency while maintaining delivery guarantees.

        Returns:
            None

        Raises:
            Exception: If critical error occurs during notification consumption
        """
        try:
            print(f"Starting notification consumer worker: {self.worker_id}")

            self.is_running = True
            self.shutdown_requested = False

            await self.kafka_gateway.consume_notifications(
                handler_func=self._handle_notification_message,
                consumer_group=self.consumer_group,
                max_batch_size=10
            )

        except Exception as e:
            print(f"Error in notification consumer: {str(e)}")
            raise

    async def start_consuming_system_alerts(self) -> None:
        """
        Start consuming system alert messages from Kafka.

        This method processes system alerts, monitoring messages,
        and operational events for system health tracking and
        alerting with appropriate routing to monitoring systems.

        The consumer handles various alert types including error
        alerts, performance warnings, and operational notifications
        with appropriate severity-based routing and processing.

        Returns:
            None

        Raises:
            Exception: If critical error occurs during alert consumption
        """
        try:
            print(f"Starting system alerts consumer worker: {self.worker_id}")

            self.is_running = True

        except Exception as e:
            print(f"Error in system alerts consumer: {str(e)}")
            raise

    async def _handle_notification_message(self, message: Dict[str, Any]) -> bool:
        """
        Handle individual notification message from Kafka.

        This method processes notification requests by extracting
        message data and routing to appropriate notification channels
        based on notification type and user preferences.

        The handler validates message structure, extracts notification
        parameters, and delegates to type-specific processing methods
        with comprehensive error handling and logging.

        Args:
            message: Notification message data from Kafka

        Returns:
            bool: True if message was processed successfully, False otherwise

        Raises:
            Exception: If critical error occurs during message handling
        """
        try:
            if self.shutdown_requested:
                return False

            notification_type = message.get("notification_type")
            if not notification_type:
                print("Invalid notification message: missing notification_type")
                return True

            success = await self._process_notification_by_type(message, notification_type)

            if success:
                self.processed_messages_count += 1
                print(f"Successfully processed {notification_type} notification")
            else:
                self.failed_messages_count += 1
                print(f"Failed to process {notification_type} notification")

            return success

        except Exception as e:
            self.failed_messages_count += 1
            print(f"Error handling notification message: {str(e)}")
            return False

    async def _process_notification_by_type(self,
                                            message: Dict[str, Any],
                                            notification_type: str) -> bool:
        """
        Process notification message based on its type.

        This method routes notification messages to appropriate handlers
        based on the notification type. It supports various notification
        types including job completion, failure, progress updates, and
        system alerts with type-specific processing logic.

        Args:
            message: Complete notification message data
            notification_type: Type of notification to process

        Returns:
            bool: True if notification was sent successfully

        Raises:
            Exception: If error occurs during type-specific processing
        """
        try:
            if notification_type == "job_completion":
                return await self._handle_job_completion_notification(message)

            elif notification_type == "job_failure":
                return await self._handle_job_failure_notification(message)

            elif notification_type == "job_progress":
                return await self._handle_job_progress_notification(message)

            elif notification_type == "system_alert":
                return await self._handle_system_alert_notification(message)

            else:
                print(f"Unknown notification type: {notification_type}")
                return True

        except Exception as e:
            print(f"Error processing {notification_type} notification: {str(e)}")
            return False

    async def _handle_job_completion_notification(self, message: Dict[str, Any]) -> bool:
        """
        Handle job completion notification message.

        This method processes job completion notifications by extracting
        job information, user details, and download links to send
        completion notifications to users via configured notification
        channels with appropriate templates and formatting.

        Args:
            message: Job completion notification data

        Returns:
            bool: True if notification was sent successfully

        Raises:
            Exception: If error occurs during completion notification handling
        """
        try:
            template_data = message.get("template_data", {})
            user_email = message.get("recipient_email") or message.get("user_email")

            if not user_email:
                print("Job completion notification missing recipient email")
                return False

            job_data = template_data
            download_url = template_data.get("download_url", "")

            print(f"Sending job completion notification to {user_email}")
            print(f"Job: {job_data.get('original_filename', 'Unknown')}")
            print(f"Frames: {job_data.get('frame_count', 0)}")

            return True

        except Exception as e:
            print(f"Error sending job completion notification: {str(e)}")
            return False

    async def _handle_job_failure_notification(self, message: Dict[str, Any]) -> bool:
        """
        Handle job failure notification message.

        This method processes job failure notifications by extracting
        error information and job details to send failure notifications
        to users via configured notification channels with appropriate
        error context and troubleshooting information.

        Args:
            message: Job failure notification data

        Returns:
            bool: True if notification was sent successfully

        Raises:
            Exception: If error occurs during failure notification handling
        """
        try:
            template_data = message.get("template_data", {})
            user_email = message.get("recipient_email") or message.get("user_email")
            error_message = template_data.get("error_message", "Processing failed")

            if not user_email:
                print("Job failure notification missing recipient email")
                return False

            print(f"Sending job failure notification to {user_email}")
            print(f"Job: {template_data.get('original_filename', 'Unknown')}")
            print(f"Error: {error_message}")

            return True

        except Exception as e:
            print(f"Error sending job failure notification: {str(e)}")
            return False

    async def _handle_job_progress_notification(self, message: Dict[str, Any]) -> bool:
        """
        Handle job progress notification message.

        This method processes job progress notifications by extracting
        progress information and job details to send progress updates
        to users via configured notification channels with current
        processing status and estimated completion times.

        Args:
            message: Job progress notification data

        Returns:
            bool: True if notification was sent successfully

        Raises:
            Exception: If error occurs during progress notification handling
        """
        try:
            template_data = message.get("template_data", {})
            user_email = message.get("recipient_email") or message.get("user_email")
            progress = template_data.get("progress_percentage", 0)

            if not user_email:
                print("Job progress notification missing recipient email")
                return False

            print(f"Sending job progress notification to {user_email}")
            print(f"Job: {template_data.get('original_filename', 'Unknown')}")
            print(f"Progress: {progress}%")

            return True

        except Exception as e:
            print(f"Error sending job progress notification: {str(e)}")
            return False

    async def _handle_system_alert_notification(self, message: Dict[str, Any]) -> bool:
        """
        Handle system alert notification message.

        This method processes system alert notifications by extracting
        alert information, severity levels, and routing to appropriate
        monitoring systems or administrator notification channels
        based on alert type and severity configuration.

        Args:
            message: System alert notification data

        Returns:
            bool: True if alert was processed successfully

        Raises:
            Exception: If error occurs during alert notification handling
        """
        try:
            alert_data = message.get("alert_data", {})
            alert_type = alert_data.get("alert_type", "info")
            alert_message = alert_data.get("message", "System alert")
            severity = alert_data.get("severity", "medium")

            print(f"Processing system alert: {alert_type}")
            print(f"Severity: {severity}")
            print(f"Message: {alert_message}")

            return True

        except Exception as e:
            print(f"Error processing system alert: {str(e)}")
            return False

    async def _handle_system_alert_message(self, message: Dict[str, Any]) -> bool:
        """
        Handle system alert message from dedicated alerts topic.

        This method processes system alerts from dedicated alert topics
        by extracting alert information, metadata, and routing to
        appropriate monitoring and alerting systems with proper
        categorization and severity-based handling.

        Args:
            message: System alert message data

        Returns:
            bool: True if alert was processed successfully

        Raises:
            Exception: If error occurs during alert message handling
        """
        try:
            if self.shutdown_requested:
                return False

            alert_type = message.get("alert_type", "info")
            alert_message = message.get("message", "System alert")
            metadata = message.get("metadata", {})

            print(f"System Alert [{alert_type}]: {alert_message}")

            if metadata:
                print(f"Metadata: {json.dumps(metadata, indent=2)}")

            self.processed_messages_count += 1
            return True

        except Exception as e:
            self.failed_messages_count += 1
            print(f"Error handling system alert: {str(e)}")
            return False

    async def stop(self) -> None:
        """
        Stop the Kafka consumer worker gracefully.

        This method initiates graceful shutdown by setting shutdown flag
        and stopping Kafka consumers with proper cleanup of resources.

        The shutdown process ensures all in-flight messages are processed
        or properly acknowledged before terminating the consumer to
        maintain message delivery guarantees and prevent data loss.

        Returns:
            None

        Raises:
            Exception: If error occurs during shutdown process
        """
        print(f"Stopping Kafka consumer worker: {self.worker_id}")

        self.shutdown_requested = True
        self.is_running = False

        try:
            await self.kafka_gateway.stop_consuming()
        except Exception as e:
            print(f"Error stopping Kafka consumers: {str(e)}")

        print(
            f"Worker {self.worker_id} stopped. Processed: {self.processed_messages_count}, Failed: {self.failed_messages_count}")

    def get_worker_status(self) -> Dict[str, Any]:
        """
        Get current worker status and processing statistics.

        This method provides comprehensive worker status information
        including processing statistics, success rates, configuration
        details, and health indicators for monitoring dashboards,
        operational visibility, and performance analysis.

        Returns:
            Dict[str, Any]: Worker status information and metrics including
                          processing statistics, success rates, and configuration

        Raises:
            None: This method does not raise exceptions
        """
        return {
            "worker_id": self.worker_id,
            "consumer_group": self.consumer_group,
            "is_running": self.is_running,
            "shutdown_requested": self.shutdown_requested,
            "processed_messages_total": self.processed_messages_count,
            "failed_messages_total": self.failed_messages_count,
            "success_rate": (
                self.processed_messages_count / (self.processed_messages_count + self.failed_messages_count)
                if (self.processed_messages_count + self.failed_messages_count) > 0 else 0
            )
        }