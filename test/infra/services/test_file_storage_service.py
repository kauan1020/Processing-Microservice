import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import tempfile
import os
import subprocess
import json
from datetime import datetime

from infra.services.file_storage_service import FileStorageService
from domain.exceptions import StorageException


class TestFileStorageService:

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def service(self, temp_directory):
        return FileStorageService(
            base_storage_path=temp_directory,
            max_file_size_mb=10,
            allowed_extensions=['.mp4', '.avi', '.mov']
        )

    @pytest.mark.asyncio
    async def test_store_video_file_with_valid_file_should_store_successfully(
            self, service, temp_directory
    ):
        file_content = b"fake video content"
        filename = "test_video.mp4"
        user_id = "test-user-123"

        result = await service.store_video_file(file_content, filename, user_id)

        assert result.startswith(temp_directory)
        assert os.path.exists(result)

        with open(result, 'rb') as f:
            assert f.read() == file_content

    @pytest.mark.asyncio
    async def test_store_video_file_with_empty_content_should_raise_storage_exception(self, service):
        with pytest.raises(StorageException):
            await service.store_video_file(b"", "test.mp4", "user123")

    @pytest.mark.asyncio
    async def test_store_video_file_with_oversized_file_should_raise_storage_exception(self, service):
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB

        with pytest.raises(StorageException):
            await service.store_video_file(large_content, "large.mp4", "user123")

    @pytest.mark.asyncio
    async def test_store_video_file_with_invalid_extension_should_raise_storage_exception(self, service):
        with pytest.raises(StorageException):
            await service.store_video_file(b"content", "document.pdf", "user123")

    @pytest.mark.asyncio
    async def test_create_zip_archive_with_valid_frames_should_create_zip(
            self, service, temp_directory
    ):
        frame_files = []
        for i in range(3):
            frame_path = os.path.join(temp_directory, f"frame_{i:06d}.png")
            with open(frame_path, 'w') as f:
                f.write(f"frame {i}")
            frame_files.append(frame_path)

        output_path = os.path.join(temp_directory, "result.zip")

        zip_size = await service.create_zip_archive(frame_files, output_path)

        assert os.path.exists(output_path)
        assert zip_size > 0

    @pytest.mark.asyncio
    async def test_create_zip_archive_with_empty_frame_list_should_raise_storage_exception(
            self, service, temp_directory
    ):
        output_path = os.path.join(temp_directory, "empty.zip")

        with pytest.raises(StorageException):
            await service.create_zip_archive([], output_path)

    @pytest.mark.asyncio
    async def test_get_file_size_with_existing_file_should_return_size(
            self, service, temp_directory
    ):
        test_file = os.path.join(temp_directory, "test.txt")
        content = b"test content"

        with open(test_file, 'wb') as f:
            f.write(content)

        size = await service.get_file_size(test_file)
        assert size == len(content)

    @pytest.mark.asyncio
    async def test_get_file_size_with_nonexistent_file_should_return_zero(self, service):
        size = await service.get_file_size("/nonexistent/file.txt")
        assert size == 0

    @pytest.mark.asyncio
    async def test_delete_file_with_existing_file_should_return_true(
            self, service, temp_directory
    ):
        test_file = os.path.join(temp_directory, "test.txt")

        with open(test_file, 'w') as f:
            f.write("test")

        result = await service.delete_file(test_file)

        assert result is True
        assert not os.path.exists(test_file)

    @pytest.mark.asyncio
    async def test_delete_file_with_nonexistent_file_should_return_true(self, service):
        result = await service.delete_file("/nonexistent/file.txt")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_directory_with_existing_directory_should_return_true(
            self, service, temp_directory
    ):
        test_dir = os.path.join(temp_directory, "testdir")
        os.makedirs(test_dir)

        with open(os.path.join(test_dir, "file.txt"), 'w') as f:
            f.write("test")

        result = await service.delete_directory(test_dir)

        assert result is True
        assert not os.path.exists(test_dir)

    @pytest.mark.asyncio
    async def test_ensure_directory_exists_should_create_directory(
            self, service, temp_directory
    ):
        new_dir = os.path.join(temp_directory, "new", "nested", "directory")

        await service.ensure_directory_exists(new_dir)

        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)

    @pytest.mark.asyncio
    async def test_get_available_space_should_return_positive_number(self, service):
        space = await service.get_available_space()
        assert isinstance(space, int)
        assert space >= 0

    @pytest.mark.asyncio
    async def test_list_files_with_pattern_should_filter_correctly(
            self, service, temp_directory
    ):
        files = ["test1.txt", "test2.png", "other.doc"]

        for filename in files:
            with open(os.path.join(temp_directory, filename), 'w') as f:
                f.write("content")

        result = await service.list_files(temp_directory, "*.txt")

        assert len(result) == 1
        assert result[0].endswith("test1.txt")

    @pytest.mark.asyncio
    async def test_move_file_should_move_file_successfully(
            self, service, temp_directory
    ):
        source = os.path.join(temp_directory, "source.txt")
        destination = os.path.join(temp_directory, "destination.txt")

        with open(source, 'w') as f:
            f.write("test content")

        result = await service.move_file(source, destination)

        assert result is True
        assert not os.path.exists(source)
        assert os.path.exists(destination)

    @pytest.mark.asyncio
    async def test_copy_file_should_copy_file_successfully(
            self, service, temp_directory
    ):
        source = os.path.join(temp_directory, "source.txt")
        destination = os.path.join(temp_directory, "destination.txt")
        content = "test content"

        with open(source, 'w') as f:
            f.write(content)

        result = await service.copy_file(source, destination)

        assert result is True
        assert os.path.exists(source)
        assert os.path.exists(destination)

        with open(destination, 'r') as f:
            assert f.read() == content

    @pytest.mark.asyncio
    async def test_get_file_metadata_should_return_metadata_dict(
            self, service, temp_directory
    ):
        test_file = os.path.join(temp_directory, "metadata_test.txt")

        with open(test_file, 'w') as f:
            f.write("test content")

        metadata = await service.get_file_metadata(test_file)

        assert "size" in metadata
        assert "created_at" in metadata
        assert "modified_at" in metadata
        assert metadata["is_file"] is True

    @pytest.mark.asyncio
    async def test_store_file_with_different_content_types_should_handle_correctly(
            self, service, temp_directory
    ):
        # Test with binary content
        binary_content = b"\x00\x01\x02\x03\xff\xfe"
        filename = "binary_test.mp4"
        user_id = "user-456"

        result = await service.store_video_file(binary_content, filename, user_id)

        assert os.path.exists(result)
        with open(result, 'rb') as f:
            assert f.read() == binary_content

    @pytest.mark.asyncio
    async def test_concurrent_file_operations_should_handle_correctly(
            self, service, temp_directory
    ):
        import asyncio

        async def store_file(index):
            content = f"file content {index}".encode()
            filename = f"concurrent_test_{index}.mp4"
            return await service.store_video_file(content, filename, f"user-{index}")

        # Store multiple files concurrently
        tasks = [store_file(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Verify all files were stored
        for result in results:
            assert os.path.exists(result)

    @pytest.mark.asyncio
    async def test_handle_special_characters_in_filename_should_sanitize(
            self, service, temp_directory
    ):
        content = b"test content"
        filename = "test<>:\"|?*.mp4"  # Invalid filename characters
        user_id = "user-789"

        result = await service.store_video_file(content, filename, user_id)

        assert os.path.exists(result)
        # Verify the actual filename was sanitized
        assert not any(char in os.path.basename(result) for char in '<>:"|?*')

    @pytest.mark.asyncio
    async def test_validate_file_integrity_after_storage_should_verify_content(
            self, service, temp_directory
    ):
        original_content = b"integrity test content"
        filename = "integrity_test.mp4"
        user_id = "integrity-user"

        stored_path = await service.store_video_file(original_content, filename, user_id)

        # Verify file integrity
        with open(stored_path, 'rb') as f:
            stored_content = f.read()

        assert stored_content == original_content
        assert len(stored_content) == len(original_content)
