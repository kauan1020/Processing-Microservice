import asyncio
import subprocess
import os
import json
import tempfile
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from interfaces.services.video_processor_interface import VideoProcessorInterface
from domain.value_objects import VideoFile, FrameExtractionConfig, ProcessingResult
from domain.exceptions import FFmpegException, VideoCorruptedException, StorageException


class VideoProcessorService(VideoProcessorInterface):
    """
    FFmpeg-based implementation of VideoProcessorInterface.

    This service provides concrete implementation for video processing operations
    using FFmpeg as the underlying video processing engine with comprehensive
    error handling, resource management, and performance optimization.

    It handles video analysis, frame extraction, format validation, and
    processing time estimation while ensuring system stability and resource
    efficiency for large-scale video processing workloads.
    """

    def __init__(self,
                 ffmpeg_path: str = "ffmpeg",
                 ffprobe_path: str = "ffprobe",
                 max_concurrent_processes: int = 4,
                 process_timeout: int = 3600):
        """
        Initialize the video processor service with FFmpeg configuration.

        Args:
            ffmpeg_path: Path to FFmpeg executable
            ffprobe_path: Path to FFprobe executable
            max_concurrent_processes: Maximum concurrent FFmpeg processes
            process_timeout: Maximum processing time per job in seconds
        """
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.max_concurrent_processes = max_concurrent_processes
        self.process_timeout = process_timeout
        self.active_processes = {}
        self.process_semaphore = asyncio.Semaphore(max_concurrent_processes)

    async def extract_frames(self,
                             video_file: VideoFile,
                             config: FrameExtractionConfig) -> List[str]:
        """
        Extract frames from video file using FFmpeg with optimized settings.

        Args:
            video_file: Video file to process
            config: Frame extraction configuration

        Returns:
            List[str]: List of extracted frame file paths

        Raises:
            FFmpegException: If FFmpeg processing fails
            StorageException: If file operations fail
        """
        start_time = datetime.utcnow()
        frame_paths = []

        # Create temporary directory for frames
        with tempfile.TemporaryDirectory(prefix="video_frames_") as temp_dir:
            try:
                frame_pattern = os.path.join(temp_dir, "frame_%06d.png")

                async with self.process_semaphore:
                    ffmpeg_command = self._build_ffmpeg_command(
                        video_file, config, frame_pattern
                    )

                    process_id = f"extract_{id(video_file)}_{int(start_time.timestamp())}"

                    try:
                        self.active_processes[process_id] = True

                        result = await asyncio.wait_for(
                            self._execute_ffmpeg_command(ffmpeg_command),
                            timeout=self.process_timeout
                        )

                        if result.returncode != 0:
                            raise FFmpegException(
                                " ".join(ffmpeg_command),
                                result.stderr.decode('utf-8') if result.stderr else "Unknown error"
                            )

                    finally:
                        self.active_processes.pop(process_id, None)

                frame_paths = await self._collect_extracted_frames(temp_dir)

                if not frame_paths:
                    raise FFmpegException(
                        " ".join(ffmpeg_command),
                        "No frames were extracted from the video"
                    )

                # Move frames to permanent location
                permanent_frames = []
                frames_dir = tempfile.mkdtemp(prefix="frames_permanent_")

                for i, temp_frame_path in enumerate(frame_paths):
                    permanent_path = os.path.join(frames_dir, f"frame_{i + 1:06d}.png")
                    os.rename(temp_frame_path, permanent_path)
                    permanent_frames.append(permanent_path)

                return permanent_frames

            except asyncio.TimeoutError:
                raise FFmpegException(
                    "Frame extraction",
                    f"Processing timeout after {self.process_timeout} seconds"
                )
            except Exception as e:
                if isinstance(e, FFmpegException):
                    raise
                raise FFmpegException("Frame extraction", str(e))

    async def get_video_info(self, video_file: VideoFile) -> Dict[str, Any]:
        """
        Get comprehensive video metadata using FFprobe.

        Args:
            video_file: Video file to analyze

        Returns:
            Dict[str, Any]: Comprehensive video metadata

        Raises:
            VideoCorruptedException: If video is corrupted
            FFmpegException: If analysis fails
        """
        try:
            ffprobe_command = [
                self.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_file.file_path
            ]

            result = await self._execute_ffmpeg_command(ffprobe_command)

            if result.returncode != 0:
                error_message = result.stderr.decode('utf-8') if result.stderr else "Unknown error"
                if "Invalid data found" in error_message or "moov atom not found" in error_message:
                    raise VideoCorruptedException(video_file.file_path, error_message)
                raise FFmpegException(" ".join(ffprobe_command), error_message)

            probe_data = json.loads(result.stdout.decode('utf-8'))

            return self._parse_video_metadata(probe_data, video_file)

        except json.JSONDecodeError as e:
            raise FFmpegException("FFprobe output parsing", f"Invalid JSON output: {str(e)}")
        except Exception as e:
            if isinstance(e, (VideoCorruptedException, FFmpegException)):
                raise
            raise FFmpegException("Video analysis", str(e))

    async def validate_video_file(self, video_file: VideoFile) -> bool:
        """
        Validate video file readability and format compatibility.

        Args:
            video_file: Video file to validate

        Returns:
            bool: True if valid and processable, False otherwise
        """
        try:
            await self.get_video_info(video_file)
            return True
        except (VideoCorruptedException, FFmpegException):
            return False
        except Exception:
            return False

    async def estimate_processing_time(self,
                                       video_file: VideoFile,
                                       config: FrameExtractionConfig) -> float:
        """
        Estimate processing time based on video characteristics.

        Args:
            video_file: Video file to estimate processing for
            config: Extraction configuration

        Returns:
            float: Estimated processing time in seconds
        """
        try:
            video_info = await self.get_video_info(video_file)

            duration = video_info.get("duration", 0)
            file_size_mb = video_file.get_size_mb()
            estimated_frames = config.estimate_frame_count(duration)

            base_time_per_second = 0.5
            size_factor = min(file_size_mb / 100, 2.0)
            fps_factor = config.fps / 1.0
            quality_factor = config.quality / 95.0

            estimated_time = (
                    duration * base_time_per_second *
                    size_factor * fps_factor * quality_factor
            )

            estimated_time += estimated_frames * 0.01

            return max(estimated_time, 10.0)

        except Exception:
            return 300.0

    async def cancel_processing(self, job_id: str) -> bool:
        """
        Cancel ongoing processing for a specific job.

        Args:
            job_id: Job identifier to cancel

        Returns:
            bool: True if cancellation was successful
        """
        try:
            for process_id in list(self.active_processes.keys()):
                if job_id in process_id:
                    self.active_processes.pop(process_id, None)
                    return True
            return False
        except Exception:
            return False

    async def get_supported_formats(self) -> List[str]:
        """
        Get list of supported video formats from FFmpeg.

        Returns:
            List[str]: List of supported file extensions
        """
        return ["mp4", "avi", "mov", "mkv", "webm", "wmv", "flv", "m4v", "3gp", "ts"]

    async def optimize_for_extraction(self, video_file: VideoFile) -> Dict[str, Any]:
        """
        Analyze video and suggest optimal extraction parameters.

        Args:
            video_file: Video file to analyze

        Returns:
            Dict[str, Any]: Optimization recommendations
        """
        try:
            video_info = await self.get_video_info(video_file)

            duration = video_info.get("duration", 0)
            resolution = video_info.get("resolution", (0, 0))
            frame_rate = video_info.get("frame_rate", 30)
            file_size_mb = video_file.get_size_mb()

            recommended_fps = min(1.0, frame_rate / 30) if duration > 300 else 1.0

            if resolution[0] > 1920 or resolution[1] > 1080:
                recommended_quality = 85
                complexity = "high"
            elif resolution[0] > 1280 or resolution[1] > 720:
                recommended_quality = 90
                complexity = "medium"
            else:
                recommended_quality = 95
                complexity = "low"

            estimated_frames = int(duration * recommended_fps)
            memory_mb = max(file_size_mb * 0.1, 100)

            return {
                "recommended_fps": recommended_fps,
                "recommended_quality": recommended_quality,
                "estimated_frame_count": estimated_frames,
                "memory_requirements": memory_mb,
                "processing_complexity": complexity,
                "optimization_notes": [
                    f"Video duration: {duration:.1f}s",
                    f"Resolution: {resolution[0]}x{resolution[1]}",
                    f"Original frame rate: {frame_rate}fps",
                    f"File size: {file_size_mb:.1f}MB"
                ]
            }

        except Exception as e:
            return {
                "recommended_fps": 1.0,
                "recommended_quality": 95,
                "estimated_frame_count": 60,
                "memory_requirements": 200,
                "processing_complexity": "unknown",
                "error": str(e)
            }

    def _build_ffmpeg_command(self,
                              video_file: VideoFile,
                              config: FrameExtractionConfig,
                              output_pattern: str) -> List[str]:
        """
        Build FFmpeg command for frame extraction.

        Args:
            video_file: Input video file
            config: Extraction configuration
            output_pattern: Output file pattern

        Returns:
            List[str]: FFmpeg command arguments
        """
        command = [self.ffmpeg_path, "-y", "-i", video_file.file_path]

        if config.start_time > 0:
            command.extend(["-ss", str(config.start_time)])

        if config.end_time is not None:
            duration = config.end_time - config.start_time
            command.extend(["-t", str(duration)])

        video_filters = [f"fps={config.fps}"]

        if config.output_format.lower() in ["jpg", "jpeg"]:
            command.extend(["-q:v", str(int((100 - config.quality) / 10 + 1))])

        command.extend([
            "-vf", ",".join(video_filters),
            "-frames:v", str(config.max_frames) if config.max_frames else "999999",
            output_pattern
        ])

        return command

    async def _execute_ffmpeg_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """
        Execute FFmpeg command asynchronously.

        Args:
            command: Command and arguments to execute

        Returns:
            subprocess.CompletedProcess: Process execution result
        """
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        return subprocess.CompletedProcess(
            args=command,
            returncode=process.returncode,
            stdout=stdout,
            stderr=stderr
        )

    async def _collect_extracted_frames(self, output_directory: str) -> List[str]:
        """
        Collect paths of all extracted frame files.

        Args:
            output_directory: Directory containing extracted frames

        Returns:
            List[str]: Sorted list of frame file paths
        """
        try:
            frame_files = []
            for file_name in os.listdir(output_directory):
                if file_name.startswith("frame_") and file_name.endswith(".png"):
                    frame_files.append(os.path.join(output_directory, file_name))

            return sorted(frame_files)
        except OSError:
            return []

    def _parse_video_metadata(self, probe_data: Dict[str, Any], video_file: VideoFile) -> Dict[str, Any]:
        """
        Parse FFprobe output into structured metadata.

        Args:
            probe_data: Raw FFprobe JSON output
            video_file: Original video file information

        Returns:
            Dict[str, Any]: Structured video metadata
        """
        format_info = probe_data.get("format", {})
        video_stream = None

        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if not video_stream:
            raise VideoCorruptedException(video_file.file_path, "No video stream found")

        duration = float(format_info.get("duration", 0))
        if duration == 0 and video_stream.get("duration"):
            duration = float(video_stream["duration"])

        frame_rate = 30.0
        if video_stream.get("avg_frame_rate"):
            try:
                num, den = map(int, video_stream["avg_frame_rate"].split("/"))
                if den > 0:
                    frame_rate = num / den
            except (ValueError, ZeroDivisionError):
                pass

        return {
            "duration": duration,
            "frame_rate": frame_rate,
            "resolution": (
                int(video_stream.get("width", 0)),
                int(video_stream.get("height", 0))
            ),
            "codec": video_stream.get("codec_name", "unknown"),
            "bitrate": int(format_info.get("bit_rate", 0)),
            "format": format_info.get("format_name", "unknown"),
            "has_audio": any(
                stream.get("codec_type") == "audio"
                for stream in probe_data.get("streams", [])
            ),
            "file_size": video_file.size_bytes,
            "creation_date": format_info.get("tags", {}).get("creation_time")
        }