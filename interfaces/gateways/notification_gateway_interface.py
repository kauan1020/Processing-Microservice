from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from domain.entities.video_job import VideoJob


class NotificationGatewayInterface(ABC):
    """
    Gateway interface for notification service integration.

    This interface defines the contract for sending notifications
    through various channels including email, SMS, push notifications,
    and webhook integrations for comprehensive user communication
    about video processing status and system events.

    The implementation should handle message templating, delivery
    tracking, retry logic, and integration with external notification
    services like AWS SES, SendGrid, or custom Lambda functions.
    """

    @abstractmethod
    async def send_job_completion_notification(self,
                                               job: VideoJob,
                                               user_email: str,
                                               download_url: str) -> bool:
        """
        Send notification when a video processing job completes successfully.

        This method sends a personalized email notification to the user
        with job completion details, processing statistics, and download
        link for the extracted frames ZIP file with professional formatting.

        Args:
            job: VideoJob entity that completed processing successfully
            user_email: Email address where notification should be sent
            download_url: Direct URL for downloading the processed results

        Returns:
            bool: True if notification was sent successfully and delivered,
                 False if sending failed due to service issues or invalid email
        """
        pass

    @abstractmethod
    async def send_job_failure_notification(self,
                                            job: VideoJob,
                                            user_email: str,
                                            error_message: str,
                                            support_url: Optional[str] = None) -> bool:
        """
        Send notification when a video processing job fails with error details.

        This method sends an informative email notification about job failure
        with user-friendly error explanations, troubleshooting suggestions,
        and support contact information for resolving processing issues.

        Args:
            job: VideoJob entity that failed during processing
            user_email: Email address where failure notification should be sent
            error_message: User-friendly error description and resolution steps
            support_url: Optional URL for technical support or help documentation

        Returns:
            bool: True if failure notification was sent and acknowledged,
                 False if notification delivery failed or email is invalid
        """
        pass

    @abstractmethod
    async def send_job_progress_notification(self,
                                             job: VideoJob,
                                             user_email: str,
                                             progress_percentage: float,
                                             estimated_completion: Optional[str] = None) -> bool:
        """
        Send progress update notification for long-running video processing jobs.

        This method sends periodic progress updates for large video files
        to keep users informed about processing status and estimated
        completion times for better user experience and transparency.

        Args:
            job: VideoJob entity currently being processed
            user_email: Email address for progress update notifications
            progress_percentage: Current processing progress from 0.0 to 100.0
            estimated_completion: Optional estimated completion time string

        Returns:
            bool: True if progress notification was delivered successfully,
                 False if notification failed or user has disabled progress updates
        """
        pass

    @abstractmethod
    async def send_system_alert(self,
                                alert_type: str,
                                message: str,
                                severity: str = "medium",
                                metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send system-level alerts for monitoring and administrative purposes.

        This method delivers critical system alerts to administrators
        and monitoring systems for issues like high error rates, resource
        exhaustion, service failures, or security incidents requiring attention.

        Args:
            alert_type: Type of alert (error, warning, info, security, performance)
            message: Detailed alert message with context and impact information
            severity: Alert severity level (low, medium, high, critical)
            metadata: Optional dictionary with additional alert context and metrics

        Returns:
            bool: True if system alert was delivered to monitoring systems,
                 False if alert delivery failed but system continues operating
        """
        pass

    @abstractmethod
    async def send_bulk_notifications(self,
                                      notifications: List[Dict[str, Any]],
                                      notification_type: str) -> Dict[str, Any]:
        """
        Send multiple notifications efficiently in batch for mass communication.

        This method handles bulk notification delivery for system-wide
        announcements, maintenance notifications, or batch job completions
        with rate limiting and delivery optimization for large user bases.

        Args:
            notifications: List of notification dictionaries with recipient and content data
            notification_type: Type of bulk notification (announcement, maintenance, batch_completion)

        Returns:
            Dict[str, Any]: Bulk delivery results containing:
                - sent_count: Number of notifications sent successfully
                - failed_count: Number of failed delivery attempts
                - failed_recipients: List of recipients where delivery failed
                - delivery_time: Total time taken for bulk delivery
                - rate_limited: Whether delivery was rate limited
        """
        pass

    @abstractmethod
    async def get_notification_preferences(self, user_email: str) -> Dict[str, Any]:
        """
        Retrieve user notification preferences for personalized communication.

        This method fetches user-specific notification settings to respect
        user preferences for communication frequency, channels, and content
        types while ensuring critical notifications are always delivered.

        Args:
            user_email: Email address to retrieve notification preferences for

        Returns:
            Dict[str, Any]: User notification preferences containing:
                - email_enabled: Whether email notifications are enabled
                - job_completion: Preference for job completion notifications
                - job_failure: Preference for failure notifications
                - progress_updates: Preference for progress notifications
                - frequency: Notification frequency preference (immediate, daily, weekly)
                - preferred_time: Preferred time for non-urgent notifications
        """
        pass

    @abstractmethod
    async def update_notification_preferences(self,
                                              user_email: str,
                                              preferences: Dict[str, Any]) -> bool:
        """
        Update user notification preferences with new settings.

        This method allows users to customize their notification experience
        by updating preferences for different types of communications
        while maintaining compliance with legal requirements for notifications.

        Args:
            user_email: Email address of user updating preferences
            preferences: Dictionary containing updated preference settings

        Returns:
            bool: True if preferences were updated successfully,
                 False if update failed due to validation or storage errors
        """
        pass

    @abstractmethod
    async def track_notification_delivery(self, notification_id: str) -> Dict[str, Any]:
        """
        Track the delivery status of a specific notification for monitoring.

        This method provides delivery tracking capabilities for notification
        auditing, troubleshooting delivery issues, and ensuring critical
        communications reach their intended recipients successfully.

        Args:
            notification_id: Unique identifier of the notification to track

        Returns:
            Dict[str, Any]: Delivery tracking information containing:
                - notification_id: Unique identifier of the tracked notification
                - status: Current delivery status (sent, delivered, failed, bounced)
                - sent_at: Timestamp when notification was sent
                - delivered_at: Timestamp when delivery was confirmed
                - recipient: Email address of the notification recipient
                - error_message: Error details if delivery failed
                - retry_count: Number of delivery retry attempts made
        """
        pass

    @abstractmethod
    async def get_delivery_statistics(self,
                                      start_date: str,
                                      end_date: str) -> Dict[str, Any]:
        """
        Get comprehensive notification delivery statistics for analytics.

        This method provides detailed metrics about notification delivery
        performance, success rates, and user engagement for system
        monitoring and optimization of communication strategies.

        Args:
            start_date: Start date for statistics period in ISO format
            end_date: End date for statistics period in ISO format

        Returns:
            Dict[str, Any]: Delivery statistics containing:
                - total_sent: Total number of notifications sent
                - successful_deliveries: Number of successful deliveries
                - failed_deliveries: Number of failed delivery attempts
                - bounce_rate: Percentage of notifications that bounced
                - open_rate: Percentage of notifications opened by recipients
                - click_rate: Percentage of notifications with link clicks
                - by_type: Breakdown of statistics by notification type
                - by_day: Daily breakdown of delivery metrics
        """
        pass