from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pathlib import Path


class FileStorageInterface(ABC):
    """
    Service interface for file storage operations.

    This interface defines the contract for file storage operations
    including video upload, frame storage, ZIP file creation, and
    comprehensive file management with security and integrity checks.

    The implementation should handle local file system or cloud storage
    operations with proper error handling, security measures, and
    efficient storage utilization for large video files and frame datasets.
    """

    @abstractmethod
    async def store_video_file(self,
                               file_content: bytes,
                               filename: str,
                               user_id: str) -> str:
        """
        Store an uploaded video file securely with user isolation.

        This method saves the video file content to storage with proper
        user-based directory structure, unique naming to prevent conflicts,
        and security validation to ensure file integrity and prevent
        malicious uploads that could compromise system security.

        Args:
            file_content: Binary content of the video file to store
            filename: Original filename provided by the user for reference
            user_id: Unique identifier of the user uploading the file for isolation

        Returns:
            str: Absolute path to the stored video file in the storage system

        Raises:
            StorageException: If storage operation fails due to disk space,
                            permissions, or file system errors
            ValueError: If file content is empty or filename is invalid
        """
        pass

    @abstractmethod
    async def create_zip_archive(self,
                                 frame_files: List[str],
                                 output_path: str,
                                 compression_level: int = 6) -> int:
        """
        Create a compressed ZIP archive containing extracted video frames.

        This method creates a ZIP file containing all extracted frame images
        with optimized compression settings for balance between file size
        and creation speed, including proper file naming and metadata.

        Args:
            frame_files: List of absolute paths to frame image files to include
            output_path: Absolute path where the ZIP file should be created
            compression_level: ZIP compression level from 0 (no compression) to 9 (maximum)

        Returns:
            int: Size of the created ZIP file in bytes for storage tracking

        Raises:
            StorageException: If ZIP creation fails due to file access issues,
                            insufficient disk space, or compression errors
        """
        pass

    @abstractmethod
    async def get_file_size(self, file_path: str) -> int:
        """
        Get the size of a file in bytes with error handling.

        This method safely retrieves file size information while handling
        cases where files might be temporarily locked, moved, or deleted
        during concurrent operations in the processing system.

        Args:
            file_path: Absolute path to the file to measure

        Returns:
            int: File size in bytes, or 0 if file does not exist

        Raises:
            StorageException: If file cannot be accessed due to permission
                            issues or file system errors
        """
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """
        Delete a single file from storage with safety checks.

        This method safely removes a file from the storage system
        while handling concurrent access scenarios and ensuring
        that critical system files are protected from accidental deletion.

        Args:
            file_path: Absolute path to the file to delete

        Returns:
            bool: True if file was successfully deleted or did not exist,
                 False if deletion failed due to permissions or locks
        """
        pass

    @abstractmethod
    async def delete_directory(self, directory_path: str, recursive: bool = True) -> bool:
        """
        Delete a directory and optionally all its contents recursively.

        This method removes directories used for temporary processing
        files while ensuring safe deletion that doesn't affect other
        concurrent operations or critical system directories.

        Args:
            directory_path: Absolute path to the directory to delete
            recursive: Whether to delete directory contents recursively

        Returns:
            bool: True if directory was successfully deleted or did not exist,
                 False if deletion failed due to permissions or active file handles
        """
        pass

    @abstractmethod
    async def ensure_directory_exists(self, directory_path: str) -> None:
        """
        Ensure that a directory exists, creating it with proper permissions if necessary.

        This method creates directory structures needed for file operations
        with appropriate permissions and user isolation to maintain
        security and prevent unauthorized access to processing files.

        Args:
            directory_path: Absolute path to the directory that must exist

        Raises:
            StorageException: If directory cannot be created due to permission
                            issues, invalid path, or file system errors
        """
        pass

    @abstractmethod
    async def get_available_space(self, path: Optional[str] = None) -> int:
        """
        Get available storage space in bytes for capacity planning.

        This method checks available disk space to ensure sufficient
        storage exists for processing operations and prevents jobs
        from failing due to insufficient disk space during processing.

        Args:
            path: Optional path to check space for, defaults to main storage location

        Returns:
            int: Available space in bytes on the storage device
        """
        pass

    @abstractmethod
    async def list_files(self, directory_path: str, pattern: Optional[str] = None) -> List[str]:
        """
        List files in a directory with optional pattern filtering.

        This method provides file listing capabilities for cleanup operations,
        monitoring, and validation tasks while handling large directories
        efficiently and supporting pattern-based filtering.

        Args:
            directory_path: Absolute path to the directory to list
            pattern: Optional glob pattern to filter files (e.g., "*.png")

        Returns:
            List[str]: List of absolute paths to files matching the criteria
        """
        pass

    @abstractmethod
    async def move_file(self, source_path: str, destination_path: str) -> bool:
        """
        Move a file from source to destination location atomically.

        This method performs atomic file moves to ensure data integrity
        during processing operations and prevents partial file states
        that could corrupt processing results or cause system issues.

        Args:
            source_path: Absolute path to the source file to move
            destination_path: Absolute path where the file should be moved

        Returns:
            bool: True if file was successfully moved, False otherwise

        Raises:
            StorageException: If move operation fails due to permissions,
                            cross-device moves, or destination conflicts
        """
        pass

    @abstractmethod
    async def copy_file(self, source_path: str, destination_path: str) -> bool:
        """
        Copy a file from source to destination with integrity verification.

        This method creates file copies with verification to ensure
        data integrity and provides backup capabilities for critical
        processing files before potentially destructive operations.

        Args:
            source_path: Absolute path to the source file to copy
            destination_path: Absolute path where the copy should be created

        Returns:
            bool: True if file was successfully copied and verified, False otherwise

        Raises:
            StorageException: If copy operation fails due to insufficient space,
                            permissions, or verification failures
        """
        pass

    @abstractmethod
    async def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Get comprehensive metadata information about a file.

        This method retrieves file system metadata including timestamps,
        permissions, and other attributes useful for monitoring,
        auditing, and cleanup operations in the processing system.

        Args:
            file_path: Absolute path to the file to examine

        Returns:
            Dict[str, Any]: Dictionary containing file metadata:
                - size: File size in bytes
                - created_at: File creation timestamp
                - modified_at: Last modification timestamp
                - accessed_at: Last access timestamp
                - permissions: File permissions as octal string
                - owner: File owner information if available

        Raises:
            StorageException: If file cannot be accessed or metadata retrieval fails
        """
        pass