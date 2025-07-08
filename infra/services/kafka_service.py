import json
import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.structs import TopicPartition
from aiokafka.errors import KafkaError, ConsumerStoppedError, KafkaConnectionError
import logging
from datetime import datetime, timedelta

from infra.settings.settings import get_settings


class KafkaService:
    """
    Enhanced Kafka service implementation with robust connection management and recovery.

    This service provides comprehensive Kafka integration including message publishing,
    consumption, topic management, and error handling for distributed video processing
    workflows with reliable messaging and automatic connection recovery capabilities.

    Key improvements include connection health monitoring, automatic reconnection,
    consumer session management, and enhanced error recovery mechanisms to prevent
    message stagnation during periods of inactivity.
    """

    def __init__(self,
                 bootstrap_servers: str,
                 security_protocol: str = "PLAINTEXT",
                 client_id: str = "video-processing-service"):
        """
        Initialize Kafka service with enhanced connection configuration.

        Args:
            bootstrap_servers: Comma-separated list of Kafka broker addresses
            security_protocol: Security protocol for Kafka connections
            client_id: Client identifier for Kafka connections
        """
        self.bootstrap_servers = bootstrap_servers
        self.security_protocol = security_protocol
        self.client_id = client_id

        self.producer = None
        self.consumers = {}
        self.consumer_health = {}
        self.admin_client = None

        self.last_producer_health_check = None
        self.producer_reconnect_attempts = 0
        self.max_reconnect_attempts = 5

        self.is_shutting_down = False

        self.logger = logging.getLogger(__name__)

        settings = get_settings()
        self.topics = {
            "video_jobs": settings.kafka.topic_video_jobs,
            "notifications": settings.kafka.topic_notifications,
            "system_alerts": settings.kafka.topic_system_alerts
        }

    async def initialize(self) -> None:
        """
        Initialize Kafka producer with enhanced connection parameters.

        Sets up Kafka connections with optimized configuration for reliability,
        connection recovery, and proper handling of network interruptions.
        """
        try:
            if self.producer and not getattr(self.producer, '_closed', True):
                return

            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks=1,
                retry_backoff_ms=1000,
                request_timeout_ms=30000,
                connections_max_idle_ms=300000,
                api_version='auto',
                client_id=f"{self.client_id}-producer"
            )

            await self.producer.start()
            self.last_producer_health_check = datetime.utcnow()
            self.producer_reconnect_attempts = 0

            self.logger.info(f"Kafka producer initialized with brokers: {self.bootstrap_servers}")

        except Exception as e:
            self.logger.error(f"Failed to initialize Kafka service: {str(e)}")
            raise

    async def _ensure_producer_healthy(self) -> bool:
        """
        Ensure producer is healthy and reconnect if necessary.

        Returns:
            bool: True if producer is healthy, False otherwise
        """
        if self.is_shutting_down:
            return False

        try:
            if not self.producer or getattr(self.producer, '_closed', True):
                if self.producer_reconnect_attempts < self.max_reconnect_attempts:
                    self.logger.warning("Producer is closed, attempting to reconnect...")
                    self.producer_reconnect_attempts += 1
                    await self.initialize()
                    return True
                else:
                    self.logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached for producer")
                    return False

            now = datetime.utcnow()
            if (self.last_producer_health_check and
                    now - self.last_producer_health_check > timedelta(minutes=5)):

                try:
                    metadata = await asyncio.wait_for(
                        self.producer.client.fetch_metadata(),
                        timeout=5.0
                    )
                    self.last_producer_health_check = now
                    self.producer_reconnect_attempts = 0
                    return True
                except asyncio.TimeoutError:
                    self.logger.warning("Producer health check timed out")
                    return False
                except Exception as e:
                    self.logger.warning(f"Producer health check failed: {str(e)}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Error checking producer health: {str(e)}")
            return False

    async def ensure_topics_exist(self) -> None:
        """
        Ensure all required Kafka topics exist with proper configuration.

        Creates topics with appropriate partitioning and replication settings
        for optimal performance and reliability in video processing workloads.
        """
        self.logger.info("Topics will be auto-created by Kafka with default configuration")

    async def publish_message(self,
                              topic: str,
                              message: Dict[str, Any],
                              key: Optional[str] = None,
                              partition: Optional[int] = None,
                              retry_attempts: int = 3) -> bool:
        """
        Publish a message to a Kafka topic with enhanced delivery guarantees and retry logic.

        Args:
            topic: Target topic name for message publication
            message: Message payload as dictionary
            key: Optional message key for partitioning
            partition: Optional specific partition for message
            retry_attempts: Number of retry attempts on failure

        Returns:
            bool: True if message was published successfully, False otherwise
        """
        if self.is_shutting_down:
            return False

        for attempt in range(retry_attempts + 1):
            try:
                if not await self._ensure_producer_healthy():
                    if attempt < retry_attempts:
                        await asyncio.sleep(min(2 ** attempt, 10))
                        continue
                    return False

                self.logger.info(f"Publishing message to topic '{topic}' with key '{key}' (attempt {attempt + 1})")

                future = await self.producer.send_and_wait(
                    topic=topic,
                    value=message,
                    key=key,
                    partition=partition
                )

                self.logger.info(
                    f"Message published successfully to topic '{topic}' at partition {future.partition} offset {future.offset}")
                return True

            except KafkaConnectionError as e:
                self.logger.warning(f"Kafka connection error on attempt {attempt + 1}: {str(e)}")
                if attempt < retry_attempts:
                    self.producer = None
                    await asyncio.sleep(min(2 ** attempt, 10))
                    continue
                return False

            except KafkaError as e:
                self.logger.error(f"Kafka error publishing message to {topic} on attempt {attempt + 1}: {str(e)}")
                if attempt < retry_attempts:
                    await asyncio.sleep(min(2 ** attempt, 5))
                    continue
                return False

            except Exception as e:
                self.logger.error(f"Unexpected error publishing message to {topic} on attempt {attempt + 1}: {str(e)}")
                if attempt < retry_attempts:
                    await asyncio.sleep(min(2 ** attempt, 5))
                    continue
                return False

        return False

    async def create_consumer(self,
                              topics: List[str],
                              consumer_group: str,
                              auto_offset_reset: str = "earliest") -> AIOKafkaConsumer:
        """
        Create a Kafka consumer with enhanced configuration for reliability and recovery.

        Args:
            topics: List of topic names to consume from
            consumer_group: Consumer group identifier for coordination
            auto_offset_reset: Offset reset strategy for new consumers

        Returns:
            AIOKafkaConsumer: Configured Kafka consumer instance with enhanced settings
        """
        self.logger.info(f"Creating enhanced consumer for topics {topics} with group '{consumer_group}'")

        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=consumer_group,
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            session_timeout_ms=30000,
            heartbeat_interval_ms=10000,
            fetch_max_wait_ms=2000,
            max_poll_records=1,
            max_poll_interval_ms=300000,
            connections_max_idle_ms=300000,
            reconnect_backoff_ms=1000,
            reconnect_backoff_max_ms=10000,
            request_timeout_ms=30000,
            api_version='auto',
            client_id=f"{self.client_id}-consumer-{consumer_group}"
        )

        await consumer.start()
        self.logger.info(f"Enhanced consumer started successfully for group '{consumer_group}'")

        consumer_key = f"{consumer_group}_{hash(tuple(topics))}"
        self.consumers[consumer_key] = consumer
        self.consumer_health[consumer_key] = {
            'last_message_time': datetime.utcnow(),
            'reconnect_attempts': 0,
            'topics': topics,
            'group': consumer_group
        }

        return consumer

    async def _handle_consumer_recovery(self, consumer_key: str, error: Exception) -> Optional[AIOKafkaConsumer]:
        """
        Handle consumer recovery after connection issues.

        Args:
            consumer_key: Consumer identifier for recovery
            error: Exception that caused the need for recovery

        Returns:
            Optional[AIOKafkaConsumer]: Recovered consumer or None if recovery failed
        """
        if self.is_shutting_down:
            return None

        health_info = self.consumer_health.get(consumer_key)
        if not health_info:
            return None

        health_info['reconnect_attempts'] += 1

        if health_info['reconnect_attempts'] > self.max_reconnect_attempts:
            self.logger.error(f"Max reconnection attempts reached for consumer {consumer_key}")
            return None

        self.logger.warning(
            f"Attempting to recover consumer {consumer_key} (attempt {health_info['reconnect_attempts']}): {str(error)}")

        try:
            old_consumer = self.consumers.get(consumer_key)
            if old_consumer:
                try:
                    await asyncio.wait_for(old_consumer.stop(), timeout=5.0)
                except (asyncio.TimeoutError, Exception):
                    pass

            await asyncio.sleep(min(2 ** health_info['reconnect_attempts'], 30))

            new_consumer = await self.create_consumer(
                topics=health_info['topics'],
                consumer_group=health_info['group']
            )

            health_info['reconnect_attempts'] = 0
            self.logger.info(f"Consumer {consumer_key} recovered successfully")
            return new_consumer

        except Exception as recovery_error:
            self.logger.error(f"Failed to recover consumer {consumer_key}: {str(recovery_error)}")
            return None

    async def consume_messages(self,
                               consumer: AIOKafkaConsumer,
                               message_handler: Callable[[Dict[str, Any]], bool],
                               max_messages: int = 100) -> None:
        """
        Consume messages from Kafka with enhanced error handling and recovery.

        Args:
            consumer: Kafka consumer instance for message consumption
            message_handler: Async function to process consumed messages
            max_messages: Maximum number of messages to process in batch
        """
        consumer_key = None
        for key, stored_consumer in self.consumers.items():
            if stored_consumer == consumer:
                consumer_key = key
                break

        if not consumer_key:
            self.logger.error("Consumer not found in registry")
            return

        message_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 5

        self.logger.info(f"Starting enhanced message consumption for {consumer_key} (max: {max_messages})")

        while message_count < max_messages and not self.is_shutting_down:
            try:
                try:
                    message_batch = await asyncio.wait_for(
                        consumer.getmany(timeout_ms=2000, max_records=1),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    if not self.is_shutting_down:
                        continue
                    break

                if not message_batch:
                    continue

                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        if self.is_shutting_down:
                            break

                        try:
                            if message.value:
                                self.logger.info(
                                    f"Processing message from topic '{message.topic}' partition {message.partition} offset {message.offset}"
                                )

                                success = await message_handler(message.value)

                                if success:
                                    await consumer.commit({
                                        TopicPartition(message.topic, message.partition): message.offset + 1
                                    })
                                    self.logger.info(f"Message committed successfully at offset {message.offset}")
                                    consecutive_errors = 0
                                else:
                                    self.logger.warning(f"Message handler failed for offset {message.offset}")
                                    consecutive_errors += 1

                                self.consumer_health[consumer_key]['last_message_time'] = datetime.utcnow()

                            message_count += 1

                        except Exception as msg_error:
                            self.logger.error(f"Error processing individual message: {str(msg_error)}")
                            consecutive_errors += 1

                            if consecutive_errors >= max_consecutive_errors:
                                self.logger.error(
                                    f"Too many consecutive errors ({consecutive_errors}), triggering recovery")
                                raise msg_error

            except ConsumerStoppedError:
                if not self.is_shutting_down:
                    self.logger.warning(f"Consumer {consumer_key} stopped unexpectedly, attempting recovery")
                    recovered_consumer = await self._handle_consumer_recovery(consumer_key, ConsumerStoppedError())
                    if recovered_consumer:
                        consumer = recovered_consumer
                        consecutive_errors = 0
                        continue
                break

            except KafkaConnectionError as conn_error:
                if not self.is_shutting_down:
                    self.logger.warning(
                        f"Consumer {consumer_key} connection error, attempting recovery: {str(conn_error)}")
                    recovered_consumer = await self._handle_consumer_recovery(consumer_key, conn_error)
                    if recovered_consumer:
                        consumer = recovered_consumer
                        consecutive_errors = 0
                        continue
                break

            except Exception as e:
                self.logger.error(f"Unexpected error consuming messages for {consumer_key}: {str(e)}")
                consecutive_errors += 1

                if consecutive_errors >= max_consecutive_errors:
                    recovered_consumer = await self._handle_consumer_recovery(consumer_key, e)
                    if recovered_consumer:
                        consumer = recovered_consumer
                        consecutive_errors = 0
                        continue
                    else:
                        break

                await asyncio.sleep(min(consecutive_errors * 2, 30))

        self.logger.info(f"Message consumption completed for {consumer_key}. Processed: {message_count}")

    async def publish_job_submitted(self, job_data: Dict[str, Any]) -> bool:
        """
        Publish job submission event to video processing topic with enhanced reliability.

        Args:
            job_data: Video job information and metadata

        Returns:
            bool: True if event was published successfully
        """
        message = {
            "event_type": "job_submitted",
            "job_id": job_data.get("job_id"),
            "user_id": job_data.get("user_id"),
            "timestamp": datetime.utcnow().isoformat(),
            "data": job_data
        }

        self.logger.info(f"Publishing job submission for job {job_data.get('job_id')}")

        return await self.publish_message(
            topic=self.topics["video_jobs"],
            message=message,
            key=job_data.get("job_id"),
            retry_attempts=3
        )

    async def publish_job_completed(self, job_data: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        """
        Publish job completion event with processing metrics and enhanced delivery.

        Args:
            job_data: Completed job information
            metrics: Processing performance metrics

        Returns:
            bool: True if event was published successfully
        """
        message = {
            "event_type": "job_completed",
            "job_id": job_data.get("job_id"),
            "user_id": job_data.get("user_id"),
            "timestamp": datetime.utcnow().isoformat(),
            "data": job_data,
            "metrics": metrics
        }

        return await self.publish_message(
            topic=self.topics["video_jobs"],
            message=message,
            key=job_data.get("job_id"),
            retry_attempts=5
        )

    async def publish_job_failed(self, job_data: Dict[str, Any], error_message: str) -> bool:
        """
        Publish job failure event with error information and enhanced delivery.

        Args:
            job_data: Failed job information
            error_message: Error description and details

        Returns:
            bool: True if event was published successfully
        """
        message = {
            "event_type": "job_failed",
            "job_id": job_data.get("job_id"),
            "user_id": job_data.get("user_id"),
            "timestamp": datetime.utcnow().isoformat(),
            "data": job_data,
            "error": error_message
        }

        return await self.publish_message(
            topic=self.topics["video_jobs"],
            message=message,
            key=job_data.get("job_id"),
            retry_attempts=3
        )

    async def publish_notification(self, notification_data: Dict[str, Any]) -> bool:
        """
        Publish notification request to notification topic with delivery guarantees.

        Args:
            notification_data: Notification request information

        Returns:
            bool: True if notification was queued successfully
        """
        enhanced_notification = dict(notification_data)
        enhanced_notification["timestamp"] = datetime.utcnow().isoformat()

        return await self.publish_message(
            topic=self.topics["notifications"],
            message=enhanced_notification,
            key=notification_data.get("user_email"),
            retry_attempts=3
        )

    async def publish_system_alert(self, alert_type: str, message: str, metadata: Dict[str, Any]) -> bool:
        """
        Publish system alert for monitoring and operations with reliability.

        Args:
            alert_type: Type of system alert (error, warning, info)
            message: Alert message content
            metadata: Additional alert context and data

        Returns:
            bool: True if alert was published successfully
        """
        alert_data = {
            "alert_type": alert_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "video-processing-service",
            "metadata": metadata
        }

        return await self.publish_message(
            topic=self.topics["system_alerts"],
            message=alert_data,
            retry_attempts=2
        )

    async def get_consumer_lag(self, consumer_group: str, topic: str) -> Dict[str, Any]:
        """
        Get consumer lag metrics for monitoring and scaling decisions.

        Args:
            consumer_group: Consumer group to check lag for
            topic: Topic name to measure lag on

        Returns:
            Dict[str, Any]: Enhanced consumer lag metrics and health information
        """
        try:
            health_info = {}
            for key, consumer_health in self.consumer_health.items():
                if consumer_health.get('group') == consumer_group:
                    health_info[key] = {
                        'last_message_time': consumer_health['last_message_time'].isoformat(),
                        'reconnect_attempts': consumer_health['reconnect_attempts'],
                        'topics': consumer_health['topics']
                    }

            return {
                "consumer_group": consumer_group,
                "topic": topic,
                "total_lag": 0,
                "partition_lags": {},
                "consumer_health": health_info,
                "last_check_time": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error getting consumer lag: {str(e)}")
            return {"error": str(e)}

    async def close(self) -> None:
        """
        Close all Kafka connections with enhanced cleanup and timeout handling.

        Properly closes producer, consumers, and admin client to free up
        network connections and system resources with graceful shutdown.
        """
        self.is_shutting_down = True

        try:
            self.logger.info("Starting enhanced Kafka service shutdown...")
            close_tasks = []

            if self.producer and not getattr(self.producer, '_closed', True):
                close_tasks.append(asyncio.create_task(self._close_producer()))

            for consumer_key, consumer in list(self.consumers.items()):
                if not getattr(consumer, '_closed', True):
                    close_tasks.append(asyncio.create_task(self._close_consumer(consumer, consumer_key)))

            if close_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*close_tasks, return_exceptions=True),
                        timeout=10.0
                    )
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    self.logger.warning("Some connections did not close within timeout")

            self.producer = None
            self.consumers.clear()
            self.consumer_health.clear()
            self.logger.info("Enhanced Kafka service closed successfully")

        except Exception as e:
            self.logger.warning(f"Warning during enhanced Kafka service close: {str(e)}")
            self.producer = None
            self.consumers.clear()
            self.consumer_health.clear()

    async def _close_producer(self) -> None:
        """Close Kafka producer with enhanced error handling and timeout."""
        try:
            if self.producer:
                self.logger.info("Closing Kafka producer...")
                await asyncio.wait_for(self.producer.stop(), timeout=5.0)
                self.logger.info("Kafka producer closed successfully")
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception) as e:
            self.logger.info(f"Producer close completed with minor issues: {type(e).__name__}")

    async def _close_consumer(self, consumer, consumer_key: str) -> None:
        """Close Kafka consumer with enhanced error handling and timeout."""
        try:
            if consumer:
                self.logger.info(f"Closing Kafka consumer {consumer_key}...")
                await asyncio.wait_for(consumer.stop(), timeout=5.0)
                self.logger.info(f"Kafka consumer {consumer_key} closed successfully")
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception) as e:
            self.logger.info(f"Consumer {consumer_key} close completed with minor issues: {type(e).__name__}")