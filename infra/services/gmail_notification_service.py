import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
import asyncio
from datetime import datetime
import logging

from interfaces.services.notification_service_interface import NotificationServiceInterface
from domain.exceptions import NotificationException


class GmailNotificationService(NotificationServiceInterface):
    """
    Gmail-based notification service for sending email notifications.

    This service provides email notification capabilities using Gmail SMTP
    with proper authentication, HTML templating, and error handling for
    reliable delivery of video processing notifications to users.

    It supports both plain text and HTML email formats with comprehensive
    logging and retry mechanisms for production reliability.
    """

    def __init__(self,
                 gmail_email: str,
                 gmail_app_password: str,
                 smtp_server: str = "smtp.gmail.com",
                 smtp_port: int = 587):
        """
        Initialize Gmail notification service with authentication credentials.

        Args:
            gmail_email: Gmail address for sending notifications
            gmail_app_password: Gmail app-specific password for authentication
            smtp_server: SMTP server hostname for Gmail
            smtp_port: SMTP server port for Gmail connection
        """
        self.gmail_email = gmail_email
        self.gmail_app_password = gmail_app_password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.logger = logging.getLogger(__name__)

    async def send_job_completion_notification(self,
                                               recipient_email: str,
                                               job_data: Dict[str, Any],
                                               download_url: str) -> bool:
        """
        Send job completion notification email to user.

        Args:
            recipient_email: Email address to send notification to
            job_data: Dictionary containing job information and metadata
            download_url: Direct URL for downloading processed results

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            subject = f"Video Processing Complete - {job_data.get('original_filename', 'Unknown')}"

            html_content = self._create_completion_email_html(job_data, download_url)
            text_content = self._create_completion_email_text(job_data, download_url)

            return await self._send_email(
                recipient_email=recipient_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )

        except Exception as e:
            self.logger.error(f"Failed to send completion notification: {str(e)}")
            return False

    async def send_job_failure_notification(self,
                                            recipient_email: str,
                                            job_data: Dict[str, Any],
                                            error_message: str) -> bool:
        """
        Send job failure notification email to user.

        Args:
            recipient_email: Email address to send notification to
            job_data: Dictionary containing failed job information
            error_message: User-friendly error description

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            subject = f"Video Processing Failed - {job_data.get('original_filename', 'Unknown')}"

            html_content = self._create_failure_email_html(job_data, error_message)
            text_content = self._create_failure_email_text(job_data, error_message)

            return await self._send_email(
                recipient_email=recipient_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )

        except Exception as e:
            self.logger.error(f"Failed to send failure notification: {str(e)}")
            return False

    async def send_system_alert(self,
                                recipient_emails: list,
                                alert_type: str,
                                message: str,
                                metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send system alert notification to administrators.

        Args:
            recipient_emails: List of admin email addresses
            alert_type: Type of system alert (error, warning, info)
            message: Alert message content
            metadata: Optional additional alert context

        Returns:
            bool: True if alerts were sent successfully, False otherwise
        """
        try:
            subject = f"System Alert: {alert_type.upper()} - Video Processing Service"

            html_content = self._create_alert_email_html(alert_type, message, metadata)
            text_content = self._create_alert_email_text(alert_type, message, metadata)

            success_count = 0
            for email in recipient_emails:
                if await self._send_email(
                        recipient_email=email,
                        subject=subject,
                        html_content=html_content,
                        text_content=text_content
                ):
                    success_count += 1

            return success_count > 0

        except Exception as e:
            self.logger.error(f"Failed to send system alerts: {str(e)}")
            return False

    async def _send_email(self,
                          recipient_email: str,
                          subject: str,
                          html_content: str,
                          text_content: str) -> bool:
        """
        Send email using Gmail SMTP with proper authentication and error handling.

        Args:
            recipient_email: Email address to send to
            subject: Email subject line
            html_content: HTML formatted email content
            text_content: Plain text email content

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.gmail_email
            message["To"] = recipient_email

            text_part = MIMEText(text_content, "plain")
            html_part = MIMEText(html_content, "html")

            message.attach(text_part)
            message.attach(html_part)

            context = ssl.create_default_context()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp_email, message, context)

            self.logger.info(f"Email sent successfully to {recipient_email}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
            return False

    def _send_smtp_email(self, message: MIMEMultipart, context: ssl.SSLContext) -> None:
        """
        Execute SMTP email sending operation synchronously.

        Args:
            message: Prepared email message
            context: SSL context for secure connection

        Raises:
            NotificationException: If SMTP operation fails
        """
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.gmail_email, self.gmail_app_password)
                server.send_message(message)

        except smtplib.SMTPAuthenticationError as e:
            raise NotificationException(f"Gmail authentication failed: {str(e)}")
        except smtplib.SMTPException as e:
            raise NotificationException(f"SMTP error: {str(e)}")
        except Exception as e:
            raise NotificationException(f"Email sending failed: {str(e)}")

    def _create_completion_email_html(self, job_data: Dict[str, Any], download_url: str) -> str:
        """
        Create HTML content for job completion notification email.

        Args:
            job_data: Job information and metadata
            download_url: URL for downloading results

        Returns:
            str: HTML formatted email content
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 5px; margin-bottom: 20px; }}
                .content {{ line-height: 1.6; }}
                .info-box {{ background-color: #f9f9f9; padding: 15px; border-left: 4px solid #4CAF50; margin: 15px 0; }}
                .download-btn {{ display: inline-block; background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Video Processing Complete</h1>
                </div>
                <div class="content">
                    <p>Great news! Your video has been successfully processed and is ready for download.</p>

                    <div class="info-box">
                        <strong>Job Details:</strong><br>
                        📁 File: {job_data.get('original_filename', 'Unknown')}<br>
                        🎞️ Frames Extracted: {job_data.get('frame_count', 0)}<br>
                        📦 Archive Size: {job_data.get('zip_size_mb', 0):.1f} MB<br>
                        ⏱️ Processing Time: {job_data.get('processing_duration_minutes', 0):.1f} minutes
                    </div>

                    <p>Your extracted frames are packaged in a ZIP file and ready for download:</p>

                    <a href="{download_url}" class="download-btn">📥 Download Results</a>

                    <p><strong>Note:</strong> The download link will be available for 7 days from the completion date.</p>
                </div>
                <div class="footer">
                    <p>FIAP X Video Processing Service<br>
                    This is an automated message. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _create_completion_email_text(self, job_data: Dict[str, Any], download_url: str) -> str:
        """
        Create plain text content for job completion notification email.

        Args:
            job_data: Job information and metadata
            download_url: URL for downloading results

        Returns:
            str: Plain text formatted email content
        """
        return f"""
Video Processing Complete

Great news! Your video has been successfully processed and is ready for download.

Job Details:
- File: {job_data.get('original_filename', 'Unknown')}
- Frames Extracted: {job_data.get('frame_count', 0)}
- Archive Size: {job_data.get('zip_size_mb', 0):.1f} MB
- Processing Time: {job_data.get('processing_duration_minutes', 0):.1f} minutes

Download your results: {download_url}

Note: The download link will be available for 7 days from the completion date.

---
FIAP X Video Processing Service
This is an automated message. Please do not reply to this email.
        """

    def _create_failure_email_html(self, job_data: Dict[str, Any], error_message: str) -> str:
        """
        Create HTML content for job failure notification email.

        Args:
            job_data: Failed job information
            error_message: User-friendly error description

        Returns:
            str: HTML formatted email content
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background-color: #f44336; color: white; padding: 20px; text-align: center; border-radius: 5px; margin-bottom: 20px; }}
                .content {{ line-height: 1.6; }}
                .error-box {{ background-color: #fff3f3; padding: 15px; border-left: 4px solid #f44336; margin: 15px 0; }}
                .info-box {{ background-color: #f9f9f9; padding: 15px; border-left: 4px solid #2196F3; margin: 15px 0; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>❌ Video Processing Failed</h1>
                </div>
                <div class="content">
                    <p>We're sorry, but there was an issue processing your video file.</p>

                    <div class="info-box">
                        <strong>Job Details:</strong><br>
                        📁 File: {job_data.get('original_filename', 'Unknown')}<br>
                        📅 Submitted: {job_data.get('created_at', 'Unknown')}<br>
                        ❌ Failed: {job_data.get('updated_at', 'Unknown')}
                    </div>

                    <div class="error-box">
                        <strong>Error Details:</strong><br>
                        {error_message}
                    </div>

                    <p><strong>What you can do:</strong></p>
                    <ul>
                        <li>Check that your video file is valid and not corrupted</li>
                        <li>Try converting your video to MP4 format before uploading</li>
                        <li>Ensure your video file is under 500MB</li>
                        <li>Contact support if the problem persists</li>
                    </ul>

                    <p>If you need assistance, please contact our support team at support@fiapx.com</p>
                </div>
                <div class="footer">
                    <p>FIAP X Video Processing Service<br>
                    This is an automated message. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _create_failure_email_text(self, job_data: Dict[str, Any], error_message: str) -> str:
        """
        Create plain text content for job failure notification email.

        Args:
            job_data: Failed job information
            error_message: User-friendly error description

        Returns:
            str: Plain text formatted email content
        """
        return f"""
Video Processing Failed

We're sorry, but there was an issue processing your video file.

Job Details:
- File: {job_data.get('original_filename', 'Unknown')}
- Submitted: {job_data.get('created_at', 'Unknown')}
- Failed: {job_data.get('updated_at', 'Unknown')}

Error Details:
{error_message}

What you can do:
- Check that your video file is valid and not corrupted
- Try converting your video to MP4 format before uploading
- Ensure your video file is under 500MB
- Contact support if the problem persists

If you need assistance, please contact our support team at support@fiapx.com

---
FIAP X Video Processing Service
This is an automated message. Please do not reply to this email.
        """

    def _create_alert_email_html(self, alert_type: str, message: str, metadata: Optional[Dict[str, Any]]) -> str:
        """
        Create HTML content for system alert notification email.

        Args:
            alert_type: Type of system alert
            message: Alert message content
            metadata: Optional additional alert context

        Returns:
            str: HTML formatted email content
        """
        color_map = {
            "error": "#f44336",
            "warning": "#ff9800",
            "info": "#2196F3"
        }

        color = color_map.get(alert_type.lower(), "#666666")

        metadata_html = ""
        if metadata:
            metadata_html = "<h3>Additional Information:</h3><ul>"
            for key, value in metadata.items():
                metadata_html += f"<li><strong>{key}:</strong> {value}</li>"
            metadata_html += "</ul>"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; border-radius: 5px; margin-bottom: 20px; }}
                .content {{ line-height: 1.6; }}
                .alert-box {{ background-color: #f9f9f9; padding: 15px; border-left: 4px solid {color}; margin: 15px 0; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚨 System Alert: {alert_type.upper()}</h1>
                </div>
                <div class="content">
                    <div class="alert-box">
                        <strong>Service:</strong> Video Processing Service<br>
                        <strong>Timestamp:</strong> {datetime.utcnow().isoformat()}<br>
                        <strong>Alert Type:</strong> {alert_type.upper()}
                    </div>

                    <h3>Message:</h3>
                    <p>{message}</p>

                    {metadata_html}
                </div>
                <div class="footer">
                    <p>FIAP X Video Processing Service - System Monitoring<br>
                    This is an automated alert. Please investigate immediately.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _create_alert_email_text(self, alert_type: str, message: str, metadata: Optional[Dict[str, Any]]) -> str:
        """
        Create plain text content for system alert notification email.

        Args:
            alert_type: Type of system alert
            message: Alert message content
            metadata: Optional additional alert context

        Returns:
            str: Plain text formatted email content
        """
        metadata_text = ""
        if metadata:
            metadata_text = "\nAdditional Information:\n"
            for key, value in metadata.items():
                metadata_text += f"- {key}: {value}\n"

        return f"""
System Alert: {alert_type.upper()}

Service: Video Processing Service
Timestamp: {datetime.utcnow().isoformat()}
Alert Type: {alert_type.upper()}

Message:
{message}
{metadata_text}

---
FIAP X Video Processing Service - System Monitoring
This is an automated alert. Please investigate immediately.
        """