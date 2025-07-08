class ProcessingException(Exception):
    """Base exception for video processing operations."""

    def __init__(self, message: str, details: str = None):
        """
        Initialize processing exception with message and optional details.

        Args:
            message: Error message describing the exception
            details: Optional additional error details
        """
        self.message = message
        self.details = details
        super().__init__(self.message)


class VideoJobNotFoundException(ProcessingException):
    """Exception raised when a video job is not found."""

    def __init__(self, job_id: str):
        """
        Initialize video job not found exception.

        Args:
            job_id: ID of the job that was not found
        """
        message = f"Video job with ID '{job_id}' not found"
        super().__init__(message)
        self.job_id = job_id


class AuthorizationException(ProcessingException):
    """Exception raised for authorization failures."""

    def __init__(self, user_id: str, resource: str, action: str):
        """
        Initialize authorization exception.

        Args:
            user_id: ID of the user attempting the action
            resource: Resource being accessed
            action: Action being attempted
        """
        message = f"User '{user_id}' not authorized to {action} {resource}"
        super().__init__(message)
        self.user_id = user_id
        self.resource = resource
        self.action = action


class InvalidJobStatusException(ProcessingException):
    """Exception raised for invalid job status operations."""

    def __init__(self, job_id: str, current_status: str, required_status: str):
        """
        Initialize invalid job status exception.

        Args:
            job_id: ID of the job
            current_status: Current status of the job
            required_status: Required status for the operation
        """
        message = f"Job '{job_id}' has status '{current_status}', but '{required_status}' is required"
        super().__init__(message)
        self.job_id = job_id
        self.current_status = current_status
        self.required_status = required_status


class StorageException(ProcessingException):
    """Exception raised for file storage operations."""

    def __init__(self, operation: str, file_path: str, details: str):
        """
        Initialize storage exception.

        Args:
            operation: Storage operation that failed (store, delete, move, etc.)
            file_path: Path of the file involved in the operation
            details: Detailed error information
        """
        message = f"Storage operation '{operation}' failed for file '{file_path}'"
        super().__init__(message, details)
        self.operation = operation
        self.file_path = file_path


class InvalidVideoFormatException(ProcessingException):
    """Exception raised for invalid video format."""

    def __init__(self, filename: str, format_detected: str = None):
        """
        Initialize invalid video format exception.

        Args:
            filename: Name of the invalid video file
            format_detected: Detected format if available
        """
        message = f"Invalid video format for file '{filename}'"
        if format_detected:
            message += f" (detected: {format_detected})"
        super().__init__(message)
        self.filename = filename
        self.format_detected = format_detected


class VideoCorruptedException(ProcessingException):
    """Exception raised when video file is corrupted."""

    def __init__(self, file_path: str, details: str):
        """
        Initialize video corrupted exception.

        Args:
            file_path: Path to the corrupted video file
            details: Details about the corruption
        """
        message = f"Video file is corrupted: {file_path}"
        super().__init__(message, details)
        self.file_path = file_path


class FFmpegException(ProcessingException):
    """Exception raised for FFmpeg processing errors."""

    def __init__(self, command: str, error_output: str):
        """
        Initialize FFmpeg exception.

        Args:
            command: FFmpeg command that failed
            error_output: Error output from FFmpeg
        """
        message = f"FFmpeg processing failed: {command}"
        super().__init__(message, error_output)
        self.command = command
        self.error_output = error_output


class NotificationException(ProcessingException):
    """Exception raised for notification operations."""

    def __init__(self, message: str, notification_type: str = None, recipient: str = None):
        """
        Initialize notification exception.

        Args:
            message: Error message
            notification_type: Type of notification that failed
            recipient: Recipient email that failed
        """
        super().__init__(message)
        self.notification_type = notification_type
        self.recipient = recipient


class QueueException(ProcessingException):
    """Exception raised for queue operations."""

    def __init__(self, operation: str, details: str):
        """
        Initialize queue exception.

        Args:
            operation: Queue operation that failed
            details: Detailed error information
        """
        message = f"Queue operation '{operation}' failed"
        super().__init__(message, details)
        self.operation = operation


class WorkerException(ProcessingException):
    """Exception raised for worker operations."""

    def __init__(self, worker_id: str, operation: str, details: str):
        """
        Initialize worker exception.

        Args:
            worker_id: ID of the worker that failed
            operation: Operation that failed
            details: Detailed error information
        """
        message = f"Worker '{worker_id}' failed during '{operation}'"
        super().__init__(message, details)
        self.worker_id = worker_id
        self.operation = operation

class VideoFileNotFoundException(ProcessingException):
    """Exception raised for queue operations."""

    def __init__(self, operation: str, details: str):
        """
        Initialize queue exception.

        Args:
            operation: Queue operation that failed
            details: Detailed error information
        """
        message = f"VideoFileNotFoundException '{operation}' failed"
        super().__init__(message, details)
        self.operation = operation