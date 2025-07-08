from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class NotificationServiceInterface(ABC):
    """
    Abstract interface for notification services.

    This interface defines the contract for sending various types of notifications
    in the video processing system. Implementations can use different notification
    channels such as email, SMS, push notifications, or messaging services.

    The interface ensures consistent notification behavior across different
    service implementations while maintaining loose coupling between the
    domain logic and notification delivery mechanisms.
    """

    @abstractmethod
    async def send_job_completion_notification(self,
                                               recipient_email: str,
                                               job_data: Dict[str, Any],
                                               download_url: str) -> bool:
        """
        Send notification when a video processing job completes successfully.

        Args:
            recipient_email: Email address where notification should be sent
            job_data: Dictionary containing job information and processing results
            download_url: Direct URL for downloading the processed video frames

        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def send_job_failure_notification(self,
                                            recipient_email: str,
                                            job_data: Dict[str, Any],
                                            error_message: str) -> bool:
        """
        Send notification when a video processing job fails.

        Args:
            recipient_email: Email address where failure notification should be sent
            job_data: Dictionary containing failed job information and metadata
            error_message: User-friendly error description with troubleshooting tips

        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def send_system_alert(self,
                                recipient_emails: list,
                                alert_type: str,
                                message: str,
                                metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send system alert notifications to administrators or monitoring systems.

        Args:
            recipient_emails: List of email addresses for system administrators
            alert_type: Type of alert (error, warning, info, critical)
            message: Detailed alert message with context and impact information
            metadata: Optional dictionary with additional alert context and metrics

        Returns:
            bool: True if alert notifications were sent successfully, False otherwise
        """
        pass