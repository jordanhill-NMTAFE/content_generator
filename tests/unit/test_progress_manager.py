#!/usr/bin/env python3
"""
Unit tests for InitProgressManager and related progress tracking functionality.
Tests individual methods in isolation with mocked file system operations.
"""

import sys
import os
import json
import unittest
import tempfile
import threading
import time
from unittest.mock import Mock, patch, mock_open
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.gptgen.progress import InitProgressManager
from src.gptgen.locking import FileLock


class TestInitProgressManager(unittest.TestCase):
    """Unit tests for InitProgressManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.progress_file = os.path.join(self.temp_dir.name, "progress.json")
        # Ensure the file exists so FileLock is used in tests
        with open(self.progress_file, "w") as f:
            f.write("{}")

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_initialization_empty_file(self):
        """Test initialization with non-existent file."""
        manager = InitProgressManager(self.progress_file)
        self.assertEqual(manager._data, {})

    def test_initialization_existing_file(self):
        """Test initialization with existing file."""
        # Create test data
        test_data = {"test_key": "test_value"}
        with open(self.progress_file, "w") as f:
            json.dump(test_data, f)

        manager = InitProgressManager(self.progress_file)
        self.assertEqual(manager._data, test_data)

    def test_initialization_corrupted_file(self):
        """Test initialization with corrupted JSON file."""
        # Create corrupted file
        with open(self.progress_file, "w") as f:
            f.write("invalid json content")

        manager = InitProgressManager(self.progress_file)
        self.assertEqual(manager._data, {})  # Should default to empty dict

    def test_get_set_operations(self):
        """Test basic get and set operations."""
        manager = InitProgressManager(self.progress_file)

        # Test get non-existent key
        self.assertIsNone(manager.get("nonexistent"))

        # Test set and get
        manager.set("test_key", "test_value")
        self.assertEqual(manager.get("test_key"), "test_value")

    def test_mark_done_and_status_checks(self):
        """Test mark_done, is_done, and get_result methods."""
        manager = InitProgressManager(self.progress_file)

        # Initially not done
        self.assertFalse(manager.is_done("task1"))
        self.assertIsNone(manager.get_result("task1"))

        # Mark as done
        manager.mark_done("task1", "result_data")

        # Check status
        self.assertTrue(manager.is_done("task1"))
        self.assertEqual(manager.get_result("task1"), "result_data")

    def test_save_and_load_persistence(self):
        """Test that data persists across manager instances."""
        # Create first manager and save data
        manager1 = InitProgressManager(self.progress_file)
        manager1.set("persistent_key", "persistent_value")
        manager1.save()

        # Create second manager and verify data persists
        manager2 = InitProgressManager(self.progress_file)
        self.assertEqual(manager2.get("persistent_key"), "persistent_value")

    def test_reset_functionality(self):
        """Test reset functionality."""
        manager = InitProgressManager(self.progress_file)

        # Add some data
        manager.set("key1", "value1")
        manager.set("key2", "value2")
        self.assertIsNotNone(manager.get("key1"))

        # Reset
        manager.reset()

        # Verify data is cleared
        self.assertIsNone(manager.get("key1"))
        self.assertIsNone(manager.get("key2"))
        self.assertEqual(manager._data, {})

    def test_atomic_operations(self):
        """Test that operations are atomic."""
        manager = InitProgressManager(self.progress_file)

        # Mock the _load method to simulate concurrent access
        original_load = manager._load
        load_called = []

        def mock_load():
            load_called.append(True)
            return original_load()

        with patch.object(manager, "_load", side_effect=mock_load):
            manager.set("test_key", "test_value")

        # Verify _load was called (indicating atomic operation)
        self.assertTrue(len(load_called) > 0)

    @patch("src.gptgen.locking.FileLock")
    def test_file_locking_integration(self, mock_file_lock):
        """Test integration with file locking."""
        mock_lock_instance = Mock()
        mock_file_lock.return_value.__enter__ = Mock(return_value=mock_lock_instance)
        mock_file_lock.return_value.__exit__ = Mock(return_value=None)

        # Use a real temporary file for progress_file
        manager = InitProgressManager(self.progress_file)
        manager.set("new_key", "new_value")

        mock_file_lock.assert_called()

    def test_thread_safety_basic(self):
        """Test basic thread safety."""
        manager = InitProgressManager(self.progress_file)
        results = []

        def worker(thread_id):
            try:
                manager.set(f"thread_{thread_id}", f"value_{thread_id}")
                value = manager.get(f"thread_{thread_id}")
                results.append((thread_id, value))
            except Exception as e:
                results.append((thread_id, f"ERROR: {e}"))

        # Create and start threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all threads completed successfully
        self.assertEqual(len(results), 5)
        for thread_id, value in results:
            self.assertEqual(value, f"value_{thread_id}")

    def test_large_data_handling(self):
        """Test handling of large data structures."""
        manager = InitProgressManager(self.progress_file)

        # Create large data structure
        large_data = {f"key_{i}": f"value_{i}" * 100 for i in range(1000)}

        manager.set("large_data", large_data)
        retrieved_data = manager.get("large_data")

        self.assertEqual(retrieved_data, large_data)

    def test_json_serialization_edge_cases(self):
        """Test JSON serialization with various data types."""
        manager = InitProgressManager(self.progress_file)

        test_cases = [
            ("string", "test_string"),
            ("integer", 42),
            ("float", 3.14),
            ("boolean", True),
            ("list", [1, 2, 3, "four"]),
            ("dict", {"nested": {"data": "value"}}),
            ("null", None),
        ]

        for key, value in test_cases:
            manager.set(key, value)
            retrieved = manager.get(key)
            self.assertEqual(retrieved, value, f"Failed for {key}: {value}")

    def test_concurrent_file_access_simulation(self):
        """Test simulation of concurrent file access."""
        manager1 = InitProgressManager(self.progress_file)
        manager2 = InitProgressManager(self.progress_file)

        # Simulate concurrent writes
        manager1.set("key1", "value1")
        manager2.set("key2", "value2")

        # Both managers should see both values after reload
        manager1._load()
        manager2._load()

        self.assertIn("key1", manager1._data)
        self.assertIn("key2", manager1._data)
        self.assertIn("key1", manager2._data)
        self.assertIn("key2", manager2._data)


class TestFileLock(unittest.TestCase):
    """Unit tests for FileLock utility."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test_lock.txt")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_file_lock_creation(self):
        """Test FileLock can be created."""
        lock = FileLock(self.test_file)
        self.assertEqual(lock.file_path, self.test_file)

    def test_file_lock_creates_file_if_not_exists(self):
        """Test that FileLock creates file if it doesn't exist."""
        self.assertFalse(os.path.exists(self.test_file))

        with FileLock(self.test_file) as f:
            self.assertTrue(os.path.exists(self.test_file))
            self.assertIsNotNone(f)

    @patch("platform.system")
    def test_windows_detection(self, mock_system):
        """Test Windows platform detection."""
        mock_system.return_value = "Windows"
        lock = FileLock(self.test_file)
        self.assertTrue(lock.is_windows)

    @patch("platform.system")
    def test_unix_detection(self, mock_system):
        """Test Unix/Linux platform detection."""
        mock_system.return_value = "Linux"
        lock = FileLock(self.test_file)
        self.assertFalse(lock.is_windows)

    def test_context_manager_protocol(self):
        """Test that FileLock implements context manager protocol."""
        lock = FileLock(self.test_file)

        # Test __enter__ and __exit__ methods exist
        self.assertTrue(hasattr(lock, "__enter__"))
        self.assertTrue(hasattr(lock, "__exit__"))

        # Test context manager usage
        with lock as f:
            self.assertIsNotNone(f)
            # File should be open
            self.assertFalse(f.closed)

        # File should be closed after context
        self.assertTrue(f.closed)


if __name__ == "__main__":
    unittest.main()
