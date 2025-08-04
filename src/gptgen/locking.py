import os
import json
import fcntl
import platform
import threading
from multiprocessing import Semaphore
from typing import Optional, Dict, Any

import logging

log = logging.getLogger(__name__)


class FileLock:
    """Cross-platform file locking implementation."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.is_windows = platform.system() == "Windows"

    def __enter__(self):
        """Acquire exclusive lock."""
        # Ensure the file exists for locking
        if not os.path.exists(self.file_path):
            # Create empty file for locking
            with open(self.file_path, "w") as f:
                f.write("{}")

        self.file = open(self.file_path, "r+")

        if self.is_windows:
            # Windows file locking
            import msvcrt

            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            # Unix file locking
            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX)

        return self.file

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock."""
        try:
            if self.is_windows:
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        finally:
            self.file.close()


# Global semaphore for coordinating access across processes
# This will be shared by all InitProgressManager instances
_progress_semaphore = None


def _get_progress_semaphore():
    """Get or create the global progress semaphore."""
    global _progress_semaphore
    if _progress_semaphore is None:
        _progress_semaphore = Semaphore(1)
    return _progress_semaphore


class InitProgressManager:
    """
    Manages progress checkpointing for course initialization steps.
    Uses IPC semaphore for coordination and file locking for safety.
    Prevents simultaneous access and lost updates.
    """

    def __init__(self, progress_file: str = "init_progress.json"):
        self.progress_file = progress_file
        self._lock = threading.Lock()  # Thread-level lock for this process
        self._semaphore = _get_progress_semaphore()  # Process-level coordination
        self._data = {}
        self._load()

    def _load(self):
        """Load data from file with proper locking."""
        try:
            if os.path.exists(self.progress_file):
                with FileLock(self.progress_file) as f:
                    f.seek(0)
                    content = f.read()
                    if content.strip():
                        self._data = json.loads(content)
                    else:
                        self._data = {}
            else:
                self._data = {}
        except Exception as e:
            log.warning(f"Failed to load progress file {self.progress_file}: {e}")
            self._data = {}

    def _write(self):
        """Write data to file with proper locking and atomic operation."""
        try:
            # Ensure parent directory exists
            parent_dir = os.path.dirname(self.progress_file)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            # Use atomic write with temporary file in the same directory
            tmp_file = self.progress_file + ".tmp"

            # Write to temporary file first
            with open(tmp_file, "w") as f:
                json.dump(self._data, f, indent=2)
                f.flush()  # Ensure data is written to disk
                os.fsync(f.fileno())  # Force sync to disk

            # Atomic replace using os.replace (works on all platforms)
            os.replace(tmp_file, self.progress_file)

        except Exception as e:
            log.error(f"Failed to write progress file {self.progress_file}: {e}")
            # Clean up temporary file if it exists
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except:
                    pass

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

    def save(self):
        """Explicitly save the current data to file."""
        with self._semaphore:
            with self._lock:
                self._write()

    def mark_done(self, key, result):
        """Mark a task as done with result."""
        self.set(key, {"status": "done", "result": result})

    def is_done(self, key):
        """Check if a task is marked as done."""
        entry = self._data.get(key)
        return entry is not None and entry.get("status") == "done"

    def get_result(self, key):
        """Get the result of a completed task."""
        entry = self._data.get(key)
        if entry and entry.get("status") == "done":
            return entry.get("result")
        return None

    def reset(self):
        """Reset all progress data."""

        def operation():
            self._data = {}
            return None

        self._atomic_operation(operation)
