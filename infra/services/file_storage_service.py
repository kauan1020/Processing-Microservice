import os
import shutil
import zipfile
import aiofiles
from typing import List, Optional, Dict, Any
from pathlib import Path
import uuid
from datetime import datetime
import psutil

from interfaces.services.file_storage_interface import FileStorageInterface
from domain.exceptions import StorageException


class FileStorageService(FileStorageInterface):
    """
    Local file system implementation of FileStorageInterface.

    This service provides concrete implementation for file storage operations
    using the local file system with proper directory structure, security
    measures, and comprehensive error handling for video processing files.

    It manages video uploads, frame extraction output, ZIP archive creation,
    and cleanup operations while ensuring data integrity and system security.
    """

    def __init__(self,
                 base_storage_path: str = "./storage",
                 max_file_size_mb: int = 500,
                 allowed_extensions: Optional[List[str]] = None):
        """
        Initialize file storage service with configuration parameters.

        Args:
            base_storage_path: Base directory for all file storage operations
            max_file_size_mb: Maximum allowed file size in megabytes
            allowed_extensions: List of allowed file extensions for uploads
        """
        self.base_storage_path = Path(base_storage_path)
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.allowed_extensions = allowed_extensions or [
            '.mp4', '.avi', '.mov', '.mkv', '.webm', '.wmv', '.flv'
        ]

        self.video_path = self.base_storage_path / "videos"
        self.frames_path = self.base_storage_path / "frames"
        self.zip_path = self.base_storage_path / "results"
        self.temp_path = self.base_storage_path / "temp"

        self._ensure_directory_structure()

    def _ensure_directory_structure(self) -> None:
        """
        Ensure all required directories exist with proper permissions.

        Creates the complete directory structure needed for file storage
        operations with appropriate permissions for security and access control.
        """
        directories = [
            self.base_storage_path,
            self.video_path,
            self.frames_path,
            self.zip_path,
            self.temp_path
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True, mode=0o755)

    async def store_video_file(self,
                               file_content: bytes,
                               filename: str,
                               user_id: str) -> str:
        """
        Store an uploaded video file securely with user isolation.

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
        try:
            if not file_content:
                raise ValueError("File content cannot be empty")

            if len(file_content) > self.max_file_size_bytes:
                raise ValueError(f"File size exceeds maximum limit of {self.max_file_size_bytes // (1024 * 1024)}MB")

            file_extension = Path(filename).suffix.lower()
            if file_extension not in self.allowed_extensions:
                raise ValueError(f"File extension {file_extension} not allowed")

            user_directory = self.video_path / user_id
            await self.ensure_directory_exists(str(user_directory))

            unique_filename = f"{uuid.uuid4().hex}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{file_extension}"
            file_path = user_directory / unique_filename

            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)

            return str(file_path.absolute())

        except (ValueError, OSError) as e:
            raise StorageException("store", filename, str(e))
        except Exception as e:
            raise StorageException("store", filename, f"Unexpected error: {str(e)}")

    async def create_zip_archive(self,
                                 frame_files: List[str],
                                 output_path: str,
                                 compression_level: int = 6) -> int:
        """
        Create a compressed ZIP archive containing extracted video frames.

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
        try:
            if not frame_files:
                raise ValueError("No frame files provided for ZIP creation")

            output_dir = Path(output_path).parent
            await self.ensure_directory_exists(str(output_dir))

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=compression_level) as zipf:
                for frame_file in frame_files:
                    if os.path.exists(frame_file):
                        frame_name = Path(frame_file).name
                        zipf.write(frame_file, frame_name)
                    else:
                        print(f"Warning: Frame file not found: {frame_file}")

            if not os.path.exists(output_path):
                raise StorageException("create", output_path, "ZIP file was not created")

            zip_size = await self.get_file_size(output_path)
            return zip_size

        except (ValueError, zipfile.BadZipFile) as e:
            raise StorageException("create", output_path, str(e))
        except Exception as e:
            raise StorageException("create", output_path, f"Unexpected error: {str(e)}")

    async def get_file_size(self, file_path: str) -> int:
        """
        Get the size of a file in bytes with error handling.

        Args:
            file_path: Absolute path to the file to measure

        Returns:
            int: File size in bytes, or 0 if file does not exist

        Raises:
            StorageException: If file cannot be accessed due to permission
                            issues or file system errors
        """
        try:
            if not os.path.exists(file_path):
                return 0

            stat_result = os.stat(file_path)
            return stat_result.st_size

        except OSError as e:
            raise StorageException("access", file_path, str(e))

    async def delete_file(self, file_path: str) -> bool:
        """
        Delete a single file from storage with safety checks.

        Args:
            file_path: Absolute path to the file to delete

        Returns:
            bool: True if file was successfully deleted or did not exist,
                 False if deletion failed due to permissions or locks
        """
        try:
            if not os.path.exists(file_path):
                return True

            if not self._is_safe_to_delete(file_path):
                return False

            os.remove(file_path)
            return True

        except OSError:
            return False

    async def delete_directory(self, directory_path: str, recursive: bool = True) -> bool:
        """
        Delete a directory and optionally all its contents recursively.

        Args:
            directory_path: Absolute path to the directory to delete
            recursive: Whether to delete directory contents recursively

        Returns:
            bool: True if directory was successfully deleted or did not exist,
                 False if deletion failed due to permissions or active file handles
        """
        try:
            if not os.path.exists(directory_path):
                return True

            if not os.path.isdir(directory_path):
                return False

            if not self._is_safe_to_delete(directory_path):
                return False

            if recursive:
                shutil.rmtree(directory_path)
            else:
                os.rmdir(directory_path)

            return True

        except OSError:
            return False

    async def ensure_directory_exists(self, directory_path: str) -> None:
        """
        Ensure that a directory exists, creating it with proper permissions if necessary.

        Args:
            directory_path: Absolute path to the directory that must exist

        Raises:
            StorageException: If directory cannot be created due to permission
                            issues, invalid path, or file system errors
        """
        try:
            Path(directory_path).mkdir(parents=True, exist_ok=True, mode=0o755)

        except OSError as e:
            raise StorageException("create", directory_path, str(e))

    async def get_available_space(self, path: Optional[str] = None) -> int:
        """
        Get available storage space in bytes for capacity planning.

        Args:
            path: Optional path to check space for, defaults to main storage location

        Returns:
            int: Available space in bytes on the storage device
        """
        try:
            check_path = path or str(self.base_storage_path)
            disk_usage = psutil.disk_usage(check_path)
            return disk_usage.free

        except Exception:
            return 0

    async def list_files(self, directory_path: str, pattern: Optional[str] = None) -> List[str]:
        """
        List files in a directory with optional pattern filtering.

        Args:
            directory_path: Absolute path to the directory to list
            pattern: Optional glob pattern to filter files (e.g., "*.png")

        Returns:
            List[str]: List of absolute paths to files matching the criteria
        """
        try:
            directory = Path(directory_path)
            if not directory.exists() or not directory.is_dir():
                return []

            if pattern:
                files = list(directory.glob(pattern))
            else:
                files = [f for f in directory.iterdir() if f.is_file()]

            return [str(f.absolute()) for f in files]

        except Exception:
            return []

    async def move_file(self, source_path: str, destination_path: str) -> bool:
        """
        Move a file from source to destination location atomically.

        Args:
            source_path: Absolute path to the source file to move
            destination_path: Absolute path where the file should be moved

        Returns:
            bool: True if file was successfully moved, False otherwise

        Raises:
            StorageException: If move operation fails due to permissions,
                            cross-device moves, or destination conflicts
        """
        try:
            if not os.path.exists(source_path):
                return False

            destination_dir = Path(destination_path).parent
            await self.ensure_directory_exists(str(destination_dir))

            shutil.move(source_path, destination_path)
            return True

        except (OSError, shutil.Error) as e:
            raise StorageException("move", source_path, str(e))

    async def copy_file(self, source_path: str, destination_path: str) -> bool:
        """
        Copy a file from source to destination with integrity verification.

        Args:
            source_path: Absolute path to the source file to copy
            destination_path: Absolute path where the copy should be created

        Returns:
            bool: True if file was successfully copied and verified, False otherwise

        Raises:
            StorageException: If copy operation fails due to insufficient space,
                            permissions, or verification failures
        """
        try:
            if not os.path.exists(source_path):
                return False

            destination_dir = Path(destination_path).parent
            await self.ensure_directory_exists(str(destination_dir))

            shutil.copy2(source_path, destination_path)

            source_size = await self.get_file_size(source_path)
            dest_size = await self.get_file_size(destination_path)

            return source_size == dest_size

        except (OSError, shutil.Error) as e:
            raise StorageException("copy", source_path, str(e))

    async def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Get comprehensive metadata information about a file.

        Args:
            file_path: Absolute path to the file to examine

        Returns:
            Dict[str, Any]: Dictionary containing file metadata

        Raises:
            StorageException: If file cannot be accessed or metadata retrieval fails
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            stat_result = os.stat(file_path)

            return {
                "size": stat_result.st_size,
                "created_at": datetime.fromtimestamp(stat_result.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat_result.st_mtime).isoformat(),
                "accessed_at": datetime.fromtimestamp(stat_result.st_atime).isoformat(),
                "permissions": oct(stat_result.st_mode)[-3:],
                "is_file": os.path.isfile(file_path),
                "is_directory": os.path.isdir(file_path),
                "owner": stat_result.st_uid,
                "group": stat_result.st_gid
            }

        except (OSError, FileNotFoundError) as e:
            raise StorageException("metadata", file_path, str(e))

    def _is_safe_to_delete(self, path: str) -> bool:
        """
        Check if a path is safe to delete by validating it's within storage boundaries.

        Args:
            path: File or directory path to validate for deletion safety

        Returns:
            bool: True if path is safe to delete, False otherwise
        """
        try:
            path_obj = Path(path).resolve()
            base_path_obj = self.base_storage_path.resolve()

            return str(path_obj).startswith(str(base_path_obj))

        except Exception:
            return False

    async def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up temporary files older than specified age.

        Args:
            max_age_hours: Maximum age in hours for temporary files

        Returns:
            int: Number of files cleaned up
        """
        try:
            from datetime import timedelta

            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            cleanup_count = 0

            temp_files = await self.list_files(str(self.temp_path))

            for file_path in temp_files:
                try:
                    file_stat = os.stat(file_path)
                    file_time = datetime.fromtimestamp(file_stat.st_mtime)

                    if file_time < cutoff_time:
                        if await self.delete_file(file_path):
                            cleanup_count += 1

                except Exception:
                    continue

            return cleanup_count

        except Exception:
            return 0

    async def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive storage statistics and usage information.

        Returns:
            Dict[str, Any]: Storage statistics including usage and file counts
        """
        try:
            disk_usage = psutil.disk_usage(str(self.base_storage_path))

            video_files = await self.list_files(str(self.video_path))
            zip_files = await self.list_files(str(self.zip_path))
            temp_files = await self.list_files(str(self.temp_path))

            total_video_size = sum(
                await self.get_file_size(f) for f in video_files
            )
            total_zip_size = sum(
                await self.get_file_size(f) for f in zip_files
            )
            total_temp_size = sum(
                await self.get_file_size(f) for f in temp_files
            )

            return {
                "disk_usage": {
                    "total": disk_usage.total,
                    "used": disk_usage.used,
                    "free": disk_usage.free,
                    "percent_used": (disk_usage.used / disk_usage.total) * 100
                },
                "file_counts": {
                    "video_files": len(video_files),
                    "zip_files": len(zip_files),
                    "temp_files": len(temp_files)
                },
                "storage_usage": {
                    "video_storage_mb": total_video_size / (1024 * 1024),
                    "zip_storage_mb": total_zip_size / (1024 * 1024),
                    "temp_storage_mb": total_temp_size / (1024 * 1024),
                    "total_used_mb": (total_video_size + total_zip_size + total_temp_size) / (1024 * 1024)
                }
            }

        except Exception as e:
            return {"error": str(e)}