import os
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path


@dataclass(frozen=True)
class VideoFile:
    """
    Video file value object that encapsulates video file information and validation.

    This value object ensures video file path validity and provides methods
    for extracting file information and validation.

    Attributes:
        file_path: Full path to the video file
        original_name: Original filename provided by the user
        size_bytes: File size in bytes
    """

    file_path: str
    original_name: str
    size_bytes: int

    def __post_init__(self):
        """
        Validate video file properties after initialization.

        Raises:
            ValueError: If file path is invalid or file doesn't exist
        """
        if not self.file_path or not isinstance(self.file_path, str):
            raise ValueError("Invalid file path")

        if not os.path.exists(self.file_path):
            raise ValueError(f"Video file does not exist: {self.file_path}")

        if self.size_bytes <= 0:
            raise ValueError("File size must be greater than zero")

    def get_extension(self) -> str:
        """
        Extract file extension from the original filename.

        Returns:
            str: File extension in lowercase without the dot
        """
        return Path(self.original_name).suffix.lower().lstrip('.')

    def get_filename_without_extension(self) -> str:
        """
        Get filename without extension from original name.

        Returns:
            str: Filename without extension
        """
        return Path(self.original_name).stem

    def get_size_mb(self) -> float:
        """
        Get file size in megabytes.

        Returns:
            float: File size in MB rounded to 2 decimal places
        """
        return round(self.size_bytes / (1024 * 1024), 2)

    def is_valid_video_format(self) -> bool:
        """
        Check if the file has a valid video format extension.

        Returns:
            bool: True if extension is supported, False otherwise
        """
        valid_extensions = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'wmv', 'flv'}
        return self.get_extension() in valid_extensions

    def get_directory(self) -> str:
        """
        Get the directory path containing the video file.

        Returns:
            str: Directory path
        """
        return os.path.dirname(self.file_path)


@dataclass(frozen=True)
class FrameExtractionConfig:
    """
    Frame extraction configuration value object.

    This value object encapsulates the configuration parameters for
    video frame extraction including FPS, quality, and output settings.

    Attributes:
        fps: Frames per second to extract (default 1.0)
        output_format: Output image format (default 'png')
        quality: Output image quality 1-100 (default 95)
        start_time: Start time in seconds (default 0)
        end_time: End time in seconds (None for full video)
        max_frames: Maximum number of frames to extract (None for no limit)
    """

    fps: float = 1.0
    output_format: str = 'png'
    quality: int = 95
    start_time: float = 0.0
    end_time: Optional[float] = None
    max_frames: Optional[int] = None

    def __post_init__(self):
        """
        Validate frame extraction configuration after initialization.

        Raises:
            ValueError: If configuration parameters are invalid
        """
        if self.fps <= 0 or self.fps > 60:
            raise ValueError("FPS must be between 0.1 and 60")

        if self.output_format not in ['png', 'jpg', 'jpeg', 'bmp']:
            raise ValueError(f"Unsupported output format: {self.output_format}")

        if self.quality < 1 or self.quality > 100:
            raise ValueError("Quality must be between 1 and 100")

        if self.start_time < 0:
            raise ValueError("Start time cannot be negative")

        if self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("End time must be greater than start time")

        if self.max_frames is not None and self.max_frames <= 0:
            raise ValueError("Max frames must be positive")

    def get_ffmpeg_fps_filter(self) -> str:
        """
        Generate FFmpeg FPS filter string.

        Returns:
            str: FFmpeg filter string for frame rate
        """
        return f"fps={self.fps}"

    def get_time_range_filter(self) -> Optional[str]:
        """
        Generate FFmpeg time range filter if specified.

        Returns:
            Optional[str]: FFmpeg time filter string or None
        """
        if self.end_time is not None:
            duration = self.end_time - self.start_time
            return f"-ss {self.start_time} -t {duration}"
        elif self.start_time > 0:
            return f"-ss {self.start_time}"
        return None

    def estimate_frame_count(self, video_duration: float) -> int:
        """
        Estimate the number of frames that will be extracted.

        Args:
            video_duration: Duration of the video in seconds

        Returns:
            int: Estimated number of frames
        """
        effective_duration = video_duration - self.start_time
        if self.end_time is not None:
            effective_duration = min(effective_duration, self.end_time - self.start_time)

        estimated_frames = int(effective_duration * self.fps)

        if self.max_frames is not None:
            estimated_frames = min(estimated_frames, self.max_frames)

        return max(0, estimated_frames)


@dataclass(frozen=True)
class ProcessingResult:
    """
    Processing result value object containing the outcome of video processing.

    This value object encapsulates the results of a completed video processing
    operation including extracted frames, ZIP file information, and metrics.

    Attributes:
        frame_count: Number of frames successfully extracted
        frame_paths: List of paths to extracted frame files
        zip_file_path: Path to the generated ZIP file
        zip_file_size: Size of the ZIP file in bytes
        processing_duration: Time taken for processing in seconds
        success: Whether the processing completed successfully
        error_message: Error message if processing failed
    """

    frame_count: int
    frame_paths: List[str]
    zip_file_path: str
    zip_file_size: int
    processing_duration: float
    success: bool
    error_message: Optional[str] = None

    def __post_init__(self):
        """
        Validate processing result after initialization.

        Raises:
            ValueError: If result data is inconsistent
        """
        if self.success:
            if self.frame_count <= 0:
                raise ValueError("Successful processing must have frame count > 0")
            if not self.zip_file_path:
                raise ValueError("Successful processing must have ZIP file path")
            if self.zip_file_size <= 0:
                raise ValueError("Successful processing must have ZIP file size > 0")
        else:
            if not self.error_message:
                raise ValueError("Failed processing must have error message")

    def get_zip_size_mb(self) -> float:
        """
        Get ZIP file size in megabytes.

        Returns:
            float: ZIP file size in MB rounded to 2 decimal places
        """
        return round(self.zip_file_size / (1024 * 1024), 2)

    def get_processing_duration_minutes(self) -> float:
        """
        Get processing duration in minutes.

        Returns:
            float: Processing duration in minutes rounded to 2 decimal places
        """
        return round(self.processing_duration / 60, 2)

    def get_average_frame_processing_time(self) -> float:
        """
        Calculate average time per frame processed.

        Returns:
            float: Average seconds per frame
        """
        if self.frame_count <= 0:
            return 0.0
        return self.processing_duration / self.frame_count

    def has_frames(self) -> bool:
        """
        Check if any frames were extracted.

        Returns:
            bool: True if frames were extracted, False otherwise
        """
        return self.frame_count > 0 and len(self.frame_paths) > 0

    def validate_frame_files_exist(self) -> bool:
        """
        Validate that all frame files actually exist on disk.

        Returns:
            bool: True if all frame files exist, False otherwise
        """
        return all(os.path.exists(path) for path in self.frame_paths)

    def cleanup_frame_files(self) -> int:
        """
        Remove all extracted frame files from disk.

        Returns:
            int: Number of files successfully removed
        """
        removed_count = 0
        for frame_path in self.frame_paths:
            try:
                if os.path.exists(frame_path):
                    os.remove(frame_path)
                    removed_count += 1
            except OSError:
                continue
        return removed_count