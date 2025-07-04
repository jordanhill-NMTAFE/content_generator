from __future__ import annotations

"""Progress tracking utilities (legacy import path).

Historically the progress-tracking functionality lived in a dedicated
`progress.py` module. The implementation was later consolidated into
`locking.py` alongside other synchronisation helpers. Unfortunately, several
consumers – including the test-suite – still import it from the original path.

To preserve backwards compatibility we provide a thin wrapper around the modern
implementation that:

1. Exposes the same public API as before (`InitProgressManager`).
2. Ensures the class makes use of :pyclass:`~src.gptgen.locking.FileLock` so
   that tests which patch that symbol see their mocks invoked.

NOTE: Where possible we delegate the heavy-lifting to the underlying helpers in
`locking.py`. Any changes to the persistence logic should be done there first
and then, if necessary, reflected here.
"""

from pathlib import Path
import json
import os
import threading
from multiprocessing import Semaphore
from typing import Any, Dict, Optional

from .locking import FileLock, _get_progress_semaphore  # use canonical location
from src.utils.logger import log

__all__: list[str] = ["InitProgressManager"]


class InitProgressManager:  # pylint: disable=too-many-public-methods
    """Thread- and process-safe helper for persisting initialisation progress.

    The implementation borrows heavily from the original class that now lives
    in ``locking.py`` but replaces the direct reference to ``locking.FileLock``
    with the alias imported from :pymod:`src.gptgen.locking`. This subtle
    change ensures that *monkey-patching* the latter (as the unit tests do)
    properly intercepts lock acquisition attempts.
    """

    _DEFAULT_FILENAME = "init_progress.json"

    def __init__(self, progress_file: str | os.PathLike[str] | None = None):
        self.progress_file: str = (
            str(progress_file) if progress_file is not None else self._DEFAULT_FILENAME
        )

        # Thread-level lock for in-process mutual exclusion
        self._lock = threading.Lock()

        # Cross-process coordination shared across all instances
        self._semaphore: Semaphore = _get_progress_semaphore()

        # In-memory representation of the JSON payload
        self._data: Dict[str, Any] = {}

        # Populate _data from disk (best-effort)
        self._load()

    # ---------------------------------------------------------------------
    # Persistence helpers
    # ---------------------------------------------------------------------
    def _load(self) -> None:
        """Load JSON from *progress_file* into :pyattr:`_data`."""

        try:
            path = Path(self.progress_file)
            if path.exists():
                with FileLock(path) as fh:  # patched in tests
                    fh.seek(0)
                    raw = fh.read()
                    self._data = json.loads(raw) if raw.strip() else {}
            else:
                self._data = {}
        except Exception as exc:  # pylint: disable=broad-except
            log.warning("Failed to load progress file %s: %s", self.progress_file, exc)
            self._data = {}

    def _write(self) -> None:
        """Atomically write :pyattr:`_data` back to *progress_file*."""

        tmp_path = Path(f"{self.progress_file}.tmp")
        try:
            # Ensure parent directory exists (if any)
            tmp_path.parent.mkdir(parents=True, exist_ok=True)

            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())

            # Atomic replace is guaranteed on POSIX & Windows (Python ≥3.3)
            os.replace(tmp_path, self.progress_file)
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Failed to write progress file %s: %s", self.progress_file, exc)
            # Best-effort cleanup
            try:
                tmp_path.unlink(missing_ok=True)  # type: ignore[attr-defined]
            except Exception:  # pylint: disable=broad-except
                pass

    # ------------------------------------------------------------------
    # Public API — these mirror the original behaviour tested in the suite
    # ------------------------------------------------------------------
    def _atomic(self, fn):  # type: ignore[typing-arg-names]
        """Execute *fn* under both process- and thread-level locks."""

        with self._semaphore:
            with self._lock:
                # Refresh from disk before mutating or reading
                self._load()
                result = fn()
                self._write()
                return result

    # Basic get / set ------------------------------------------------------
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Retrieve *key* from the store (thread/process-safe)."""

        return self._atomic(lambda: self._data.get(key, default))

    def set(self, key: str, value: Any) -> None:
        """Set *key* to *value* in the persistent store."""

        self._atomic(lambda: self._data.__setitem__(key, value))

    # Convenience helpers ---------------------------------------------------
    def mark_done(self, key: str, result: Any | None = None) -> None:
        """Mark *key* as completed along with an optional *result*."""

        self.set(key, {"status": "done", "result": result})

    def is_done(self, key: str) -> bool:
        """Return *True* if *key* has been marked as completed."""

        entry = self.get(key)
        return bool(entry and isinstance(entry, dict) and entry.get("status") == "done")

    def get_result(self, key: str) -> Any:
        """Return the stored *result* for *key* if available."""

        entry = self.get(key)
        if entry and isinstance(entry, dict) and entry.get("status") == "done":
            return entry.get("result")
        return None

    # Misc ------------------------------------------------------------------
    def save(self) -> None:
        """Flush current in-memory state to disk."""

        with self._semaphore, self._lock:
            self._write()

    def reset(self) -> None:
        """Clear all stored progress information."""

        self._atomic(lambda: self._data.clear())
