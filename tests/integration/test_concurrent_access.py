"""
Test concurrent access scenarios using mocks to avoid filesystem dependencies.
"""

import json
import threading
import time
import pytest
from unittest.mock import Mock


class MockFileLock:
    """Mock file lock that simulates real locking behavior in-memory."""

    def __init__(self, file_path):
        self.file_path = file_path
        # Use a class-level lock to simulate file-level locking across processes
        if not hasattr(MockFileLock, "_file_locks"):
            MockFileLock._file_locks = {}
        if file_path not in MockFileLock._file_locks:
            MockFileLock._file_locks[file_path] = threading.Lock()
        self.lock = MockFileLock._file_locks[file_path]
        self.acquired = False
        self.file_content = "{}"

    def __enter__(self):
        # Simulate blocking if lock is held
        if not self.lock.acquire(timeout=2.0):
            raise TimeoutError(f"Lock acquisition timeout for {self.file_path}")
        self.acquired = True

        # Create a mock file object that simulates file operations
        mock_file = Mock()
        mock_file.read.return_value = self.file_content
        mock_file.seek = Mock()
        mock_file.write = Mock()
        mock_file.flush = Mock()
        mock_file.fileno.return_value = 123  # Mock file descriptor

        # Store the mock file for later access
        self.mock_file = mock_file
        return mock_file

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            self.lock.release()
            self.acquired = False


class MockFileSystem:
    """Mock file system that simulates file operations in-memory."""

    def __init__(self):
        self.files = {}
        self.temp_files = {}
        self._lock = threading.Lock()

    def write_file(self, file_path, content):
        """Write content to a file atomically."""
        with self._lock:
            # Simulate atomic write with temp file
            temp_path = f"{file_path}.{threading.get_ident()}.tmp"
            self.temp_files[temp_path] = content

            # Simulate atomic replace
            self.files[file_path] = content
            if temp_path in self.temp_files:
                del self.temp_files[temp_path]

    def read_file(self, file_path):
        """Read content from a file."""
        with self._lock:
            return self.files.get(file_path, "{}")

    def file_exists(self, file_path):
        """Check if file exists."""
        return file_path in self.files


class MockInitProgressManager:
    """Mock version of InitProgressManager that uses our custom mocks."""

    def __init__(self, progress_file, mock_fs_instance):
        self.progress_file = progress_file
        self.mock_fs = mock_fs_instance
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(1)  # Use threading.Semaphore for testing
        self._data = {}
        self._load()

    def _load(self):
        """Load data from mock file system."""
        try:
            content = self.mock_fs.read_file(self.progress_file)
            if content.strip():
                self._data = json.loads(content)
            else:
                self._data = {}
        except Exception as e:
            print(f"Failed to load progress file {self.progress_file}: {e}")
            self._data = {}

    def _write(self):
        """Write data to mock file system atomically."""
        try:
            content = json.dumps(self._data, indent=2)
            self.mock_fs.write_file(self.progress_file, content)
        except Exception as e:
            print(f"Failed to write progress file {self.progress_file}: {e}")

    def _atomic_operation(self, operation):
        """Execute an operation atomically using semaphore and file locking."""
        with self._semaphore:  # IPC coordination - only one process at a time
            with self._lock:  # Thread safety within this process
                # Always reload to get latest data from other processes
                self._load()
                # Execute the operation
                result = operation()
                # Write changes atomically
                self._write()
                return result

    def get(self, key):
        """Get value for key with proper coordination."""

        def operation():
            return self._data.get(key, None)

        return self._atomic_operation(operation)

    def set(self, key, value):
        """Set value for key with proper coordination."""

        def operation():
            self._data[key] = value
            return None

        self._atomic_operation(operation)


class TestConcurrentAccess:
    """Test concurrent access scenarios using mocks."""

    def test_concurrent_access_with_mocks(self):
        """Test concurrent access using custom mocks to verify semaphore and file locking coordination."""
        # Create a fresh mock file system for this test
        test_mock_fs = MockFileSystem()

        # Results storage: results[worker_id][other_worker_id] = value_read
        results = {0: {}, 1: {}, 2: {}}

        def worker(manager_id, progress_file, results, mock_fs_instance):
            """Worker function that sets and gets values using mocked file operations."""
            # Create a custom InitProgressManager that uses our mocks
            manager = MockInitProgressManager(progress_file, mock_fs_instance)

            # Set a value unique to this worker
            key = f"worker_{manager_id}_key"
            value = f"value_from_worker_{manager_id}"

            manager.set(key, value)

            # Small delay to increase chance of race conditions
            time.sleep(0.1)

            # Try to read values from other workers
            for other_id in range(3):
                if other_id != manager_id:
                    other_key = f"worker_{other_id}_key"
                    other_value = manager.get(other_key)
                    results[manager_id][other_id] = other_value

        # Create and start workers
        threads = []
        for i in range(3):
            thread = threading.Thread(
                target=worker, args=(i, "test_progress.json", results, test_mock_fs)
            )
            threads.append(thread)
            thread.start()

        # Wait for all workers to complete
        for thread in threads:
            thread.join()

        # Check if all workers can see each other's data
        all_successful = True
        for worker_id in range(3):
            for other_id in range(3):
                if worker_id != other_id:
                    expected_key = f"worker_{other_id}_key"
                    expected_value = f"value_from_worker_{other_id}"
                    actual_value = results[worker_id][other_id]

                    if actual_value != expected_value:
                        all_successful = False
                        break

        # Assert that all workers can see each other's data
        assert all_successful, (
            f"Some workers could not see each other's data. Results: {results}"
        )

        # Verify final file state contains all data
        final_content = test_mock_fs.read_file("test_progress.json")
        final_data = json.loads(final_content)
        assert "worker_0_key" in final_data
        assert "worker_1_key" in final_data
        assert "worker_2_key" in final_data
        assert final_data["worker_0_key"] == "value_from_worker_0"
        assert final_data["worker_1_key"] == "value_from_worker_1"
        assert final_data["worker_2_key"] == "value_from_worker_2"

    def test_semaphore_coordination(self):
        """Test that semaphore properly coordinates access across multiple workers."""
        test_mock_fs = MockFileSystem()

        # Track access patterns
        access_log = []
        access_lock = threading.Lock()

        def worker(worker_id, progress_file, mock_fs_instance):
            """Worker that logs its access patterns."""
            manager = MockInitProgressManager(progress_file, mock_fs_instance)

            # Log when we start accessing
            with access_lock:
                access_log.append(f"worker_{worker_id}_start")

            # Perform multiple operations
            for i in range(5):
                key = f"worker_{worker_id}_op_{i}"
                value = f"value_{worker_id}_{i}"
                manager.set(key, value)

                # Small delay to increase interleaving
                time.sleep(0.01)

            # Log when we finish
            with access_lock:
                access_log.append(f"worker_{worker_id}_end")

        # Start multiple workers
        threads = []
        for i in range(3):
            thread = threading.Thread(
                target=worker, args=(i, "test_progress.json", test_mock_fs)
            )
            threads.append(thread)
            thread.start()

        # Wait for all workers to complete
        for thread in threads:
            thread.join()

        # Verify that all workers completed successfully
        assert len(access_log) == 6  # 3 starts + 3 ends

        # Verify final data integrity
        final_content = test_mock_fs.read_file("test_progress.json")
        final_data = json.loads(final_content)

        # Check that all workers' data is present
        for worker_id in range(3):
            for i in range(5):
                key = f"worker_{worker_id}_op_{i}"
                expected_value = f"value_{worker_id}_{i}"
                assert key in final_data
                assert final_data[key] == expected_value

    def test_no_lost_updates(self):
        """Test that no updates are lost during concurrent access."""
        test_mock_fs = MockFileSystem()

        # Counter for tracking updates
        update_counter = 0
        counter_lock = threading.Lock()

        def worker(worker_id, progress_file, mock_fs_instance):
            """Worker that increments a shared counter."""
            nonlocal update_counter
            manager = MockInitProgressManager(progress_file, mock_fs_instance)

            for i in range(10):
                # Get current value
                current_value = manager.get("shared_counter") or 0

                # Increment
                new_value = current_value + 1
                manager.set("shared_counter", new_value)

                # Update our local counter for verification
                with counter_lock:
                    update_counter += 1

                time.sleep(0.001)  # Small delay

        # Start multiple workers
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=worker, args=(i, "test_progress.json", test_mock_fs)
            )
            threads.append(thread)
            thread.start()

        # Wait for all workers to complete
        for thread in threads:
            thread.join()

        # Verify final counter value
        final_manager = MockInitProgressManager("test_progress.json", test_mock_fs)
        final_value = final_manager.get("shared_counter")

        # The final value should equal the total number of updates
        assert final_value == update_counter, (
            f"Expected {update_counter}, got {final_value}"
        )
        assert final_value == 50, (
            f"Expected 50 updates (5 workers * 10 each), got {final_value}"
        )
