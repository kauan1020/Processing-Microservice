import smtplib
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
from datetime import datetime

from interfaces.gateways.notification_gateway_interface import NotificationGatewayInterface


class GmailNotificationService:
    def __init__(self, gmail_email: str, gmail_app_password: str):
        self.gmail_email = gmail_email
        self.gmail_app_password = gmail_app_password
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.logger = logging.getLogger(__name__)

    def _send_email_sync(self, to_email: str, subject: str, body: str) -> bool:
        try:
            msg = MIMEMultipart()
            msg['From'] = self.gmail_email
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html'))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.gmail_email, self.gmail_app_password)

            text = msg.as_string()
            server.sendmail(self.gmail_email, to_email, text)
            server.quit()

            self.logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    async def send_email(self, to_email: str, subject: str, body: str) -> bool:
        try:
            return await asyncio.to_thread(
                self._send_email_sync, to_email, subject, body
            )
        except Exception as e:
            self.logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False


class NotificationGateway(NotificationGatewayInterface):
    def __init__(self,
                 gmail_email: str,
                 gmail_app_password: str,
                 from_name: str = "FIAP X Video Processing",
                 admin_emails: Optional[List[str]] = None):
        self.gmail_service = GmailNotificationService(gmail_email, gmail_app_password)
        self.from_name = from_name
        self.admin_emails = admin_emails or []
        self.logger = logging.getLogger(__name__)

    async def send_job_completion_notification(self, notification_data: Dict[str, Any]) -> bool:
        try:
            print(f"[NOTIFICATION_GATEWAY] Received completion notification data: {notification_data}")

            user_email = notification_data.get("user_email")
            job_id = notification_data.get("job_id")
            original_filename = notification_data.get("original_filename")
            frame_count = notification_data.get("frame_count", 0)
            processing_duration = notification_data.get("processing_duration", 0)

            print(f"[NOTIFICATION_GATEWAY] Extracted user_email: '{user_email}'")
            print(f"[NOTIFICATION_GATEWAY] Job ID: {job_id}")

            if not user_email:
                print("[NOTIFICATION_GATEWAY] ERROR: No user email provided for completion notification")
                return False

            if user_email.endswith("@example.com"):
                print(f"[NOTIFICATION_GATEWAY] WARNING: Skipping notification to example email: {user_email}")
                return False

            subject = f"Video Processing Complete - {original_filename}"

            body = f"""
            <html>
            <body>
                <h2>Video Processing Complete</h2>
                <p>Your video has been successfully processed!</p>

                <h3>Job Details:</h3>
                <ul>
                    <li><strong>File:</strong> {original_filename}</li>
                    <li><strong>Job ID:</strong> {job_id}</li>
                    <li><strong>Frames Extracted:</strong> {frame_count}</li>
                    <li><strong>Processing Time:</strong> {processing_duration:.2f} seconds</li>
                </ul>

                <p>You can now download your extracted frames from the video processing service.</p>

                <p>Best regards,<br>
                {self.from_name}</p>
            </body>
            </html>
            """

            print(f"[NOTIFICATION_GATEWAY] Sending email to: {user_email}")
            print(f"[NOTIFICATION_GATEWAY] Subject: {subject}")

            success = await self.gmail_service.send_email(user_email, subject, body)

            print(f"[NOTIFICATION_GATEWAY] Email send result: {success}")
            return success

        except Exception as e:
            print(f"[NOTIFICATION_GATEWAY] ERROR: Error sending completion notification: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    async def send_job_failure_notification(self, notification_data: Dict[str, Any]) -> bool:
        try:
            print(f"[NOTIFICATION_GATEWAY] Received failure notification data: {notification_data}")

            user_email = notification_data.get("user_email")
            job_id = notification_data.get("job_id")
            original_filename = notification_data.get("original_filename")
            error_message = notification_data.get("error_message", "Unknown error")

            print(f"[NOTIFICATION_GATEWAY] Extracted user_email: '{user_email}'")

            if not user_email:
                print("[NOTIFICATION_GATEWAY] ERROR: No user email provided for failure notification")
                return False

            if user_email.endswith("@example.com"):
                print(f"[NOTIFICATION_GATEWAY] WARNING: Skipping notification to example email: {user_email}")
                return False

            subject = f"Video Processing Failed - {original_filename}"

            body = f"""
            <html>
            <body>
                <h2>Video Processing Failed</h2>
                <p>Unfortunately, your video processing job has failed.</p>

                <h3>Job Details:</h3>
                <ul>
                    <li><strong>File:</strong> {original_filename}</li>
                    <li><strong>Job ID:</strong> {job_id}</li>
                    <li><strong>Error:</strong> {error_message}</li>
                </ul>

                <p>Please try uploading your video again or contact support if the problem persists.</p>

                <p>Best regards,<br>
                {self.from_name}</p>
            </body>
            </html>
            """

            print(f"[NOTIFICATION_GATEWAY] Sending failure email to: {user_email}")

            success = await self.gmail_service.send_email(user_email, subject, body)

            print(f"[NOTIFICATION_GATEWAY] Failure email send result: {success}")
            return success

        except Exception as e:
            print(f"[NOTIFICATION_GATEWAY] ERROR: Error sending failure notification: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    async def send_system_alert(self, alert_type: str, message: str, metadata: Dict[str, Any]) -> bool:
        try:
            if not self.admin_emails:
                self.logger.info(f"System alert [{alert_type}]: {message}")
                return True

            subject = f"System Alert [{alert_type.upper()}] - Video Processing Service"

            body = f"""
            <html>
            <body>
                <h2>System Alert</h2>
                <p><strong>Alert Type:</strong> {alert_type.upper()}</p>
                <p><strong>Message:</strong> {message}</p>
                <p><strong>Timestamp:</strong> {datetime.utcnow().isoformat()}</p>

                <h3>Metadata:</h3>
                <ul>
            """

            for key, value in metadata.items():
                body += f"<li><strong>{key}:</strong> {value}</li>"

            body += f"""
                </ul>

                <p>Please investigate this alert promptly.</p>

                <p>Video Processing Service</p>
            </body>
            </html>
            """

            success_count = 0
            for admin_email in self.admin_emails:
                if await self.gmail_service.send_email(admin_email, subject, body):
                    success_count += 1

            return success_count > 0

        except Exception as e:
            self.logger.error(f"Error sending system alert: {str(e)}")
            return False

    async def send_job_progress_notification(self, notification_data: Dict[str, Any]) -> bool:
        try:
            user_email = notification_data.get("user_email")
            job_id = notification_data.get("job_id")
            original_filename = notification_data.get("original_filename")
            progress_percentage = notification_data.get("progress_percentage", 0)

            if not user_email:
                self.logger.warning("No user email provided for progress notification")
                return False

            if user_email.endswith("@example.com"):
                return False

            subject = f"Video Processing Progress - {original_filename}"

            body = f"""
            <html>
            <body>
                <h2>Video Processing Progress</h2>
                <p>Your video is being processed.</p>

                <h3>Job Details:</h3>
                <ul>
                    <li><strong>File:</strong> {original_filename}</li>
                    <li><strong>Job ID:</strong> {job_id}</li>
                    <li><strong>Progress:</strong> {progress_percentage}%</li>
                </ul>

                <p>We will notify you when processing is complete.</p>

                <p>Best regards,<br>
                {self.from_name}</p>
            </body>
            </html>
            """

            return await self.gmail_service.send_email(user_email, subject, body)

        except Exception as e:
            self.logger.error(f"Error sending progress notification: {str(e)}")
            return False

    async def send_bulk_notifications(self, notifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            results = {
                "total": len(notifications),
                "sent": 0,
                "failed": 0,
                "errors": []
            }

            for notification in notifications:
                notification_type = notification.get("type", "completion")

                try:
                    if notification_type == "completion":
                        success = await self.send_job_completion_notification(notification)
                    elif notification_type == "failure":
                        success = await self.send_job_failure_notification(notification)
                    elif notification_type == "progress":
                        success = await self.send_job_progress_notification(notification)
                    else:
                        success = False
                        results["errors"].append(f"Unknown notification type: {notification_type}")

                    if success:
                        results["sent"] += 1
                    else:
                        results["failed"] += 1

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(str(e))

            return results

        except Exception as e:
            self.logger.error(f"Error sending bulk notifications: {str(e)}")
            return {
                "total": len(notifications),
                "sent": 0,
                "failed": len(notifications),
                "errors": [str(e)]
            }

    async def get_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "email_enabled": True,
            "job_completion": True,
            "job_failure": True,
            "job_progress": False,
            "system_alerts": False
        }

    async def update_notification_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        self.logger.info(f"Notification preferences update request for user {user_id}: {preferences}")
        return True

    async def track_notification_delivery(self, notification_id: str) -> Dict[str, Any]:
        return {
            "notification_id": notification_id,
            "status": "delivered",
            "delivered_at": datetime.utcnow().isoformat(),
            "attempts": 1
        }

    async def get_delivery_statistics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        return {
            "total_sent": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "delivery_rate": 100.0,
            "period": "24h",
            "user_id": user_id
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "healthy": True,
            "service": "notification_gateway",
            "gmail_configured": bool(self.gmail_service.gmail_email and self.gmail_service.gmail_app_password),
            "admin_emails_count": len(self.admin_emails),
            "timestamp": datetime.utcnow().isoformat()
        }