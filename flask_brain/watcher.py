"""Watch a project directory for .py file changes and fire a callback (debounced)."""

import threading
from pathlib import Path
from typing import Callable, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


EXCLUDED_DIRS = {".venv", "venv", "env", "__pycache__", "node_modules", "migrations", "site-packages"}


class _ChangeHandler(FileSystemEventHandler):
    """Watchdog event handler that debounces .py changes."""

    def __init__(self, callback: Callable[[str], None], debounce: float):
        super().__init__()
        self._callback = callback
        self._debounce = debounce
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._last_path: Optional[str] = None

    def on_modified(self, event):
        self._handle(event)

    def on_created(self, event):
        self._handle(event)

    def on_moved(self, event):
        self._handle(event)

    def _handle(self, event):
        if event.is_directory:
            return
        src = event.src_path
        if not src.endswith(".py"):
            return
        # Check if path is inside an excluded directory
        parts = Path(src).parts
        for part in parts:
            if part in EXCLUDED_DIRS:
                return
        with self._lock:
            self._last_path = src
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self):
        with self._lock:
            path = self._last_path
            self._timer = None
        if path is not None:
            self._callback(path)


class ProjectWatcher:
    """Watches a project directory for Python file changes."""

    def __init__(self, path: Path, callback: Callable[[str], None], debounce: float = 2.0):
        self.path = path
        self.callback = callback
        self.debounce = debounce
        self.is_running = False
        self._observer: Optional[Observer] = None
        self._handler: Optional[_ChangeHandler] = None

    def start(self):
        """Start watching. Idempotent — safe to call twice."""
        if self.is_running:
            return
        self._handler = _ChangeHandler(self.callback, self.debounce)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.path), recursive=True)
        self._observer.start()
        self.is_running = True

    def stop(self):
        """Stop watching. Safe to call before start."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
        self.is_running = False

    def _on_change(self, event):
        """Directly invoke the handler for testing without a real Observer."""
        if self._handler is None:
            # Create a transient handler for direct test calls
            self._handler = _ChangeHandler(self.callback, self.debounce)
        self._handler._handle(event)
