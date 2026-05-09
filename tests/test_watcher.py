"""
Tests for flask_brain/watcher.py — Phase 7 Watch Mode

Coverage targets:
  - ProjectWatcher.__init__ — stores path, debounce, callback; starts stopped
  - ProjectWatcher.start() — creates Observer, starts thread, sets running flag
  - ProjectWatcher.stop() — stops Observer, clears running flag
  - ProjectWatcher._on_change() — fires callback after debounce, coalesces events
  - Debounce: rapid-fire events trigger callback only once
  - Only .py file changes trigger callback (ignore other extensions)
  - Excluded dirs (.venv, __pycache__, node_modules, migrations) are ignored
  - Double-start is idempotent (no second Observer spawned)
  - Callback receives the changed path
"""

import pytest
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call


# ── Imports ────────────────────────────────────────────────────────────────────

from flask_brain.watcher import ProjectWatcher


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_event(src_path: str, is_directory: bool = False):
    """Create a minimal watchdog-like file event."""
    evt = MagicMock()
    evt.src_path = src_path
    evt.is_directory = is_directory
    return evt


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def project_dir(tmp_path):
    """A minimal Python project directory."""
    (tmp_path / "app.py").write_text("# flask app")
    (tmp_path / "models.py").write_text("# models")
    return tmp_path


@pytest.fixture
def callback():
    return MagicMock()


# ── Construction ───────────────────────────────────────────────────────────────

class TestProjectWatcherInit:

    def test_stores_path(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback)
        assert w.path == project_dir

    def test_stores_callback(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback)
        assert w.callback is callback

    def test_default_debounce(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback)
        assert w.debounce == 2.0

    def test_custom_debounce(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback, debounce=0.1)
        assert w.debounce == 0.1

    def test_starts_not_running(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback)
        assert not w.is_running


# ── Start / Stop ───────────────────────────────────────────────────────────────

class TestProjectWatcherStartStop:

    def test_start_sets_running(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback)
        with patch("flask_brain.watcher.Observer") as MockObserver:
            MockObserver.return_value.start = MagicMock()
            w.start()
            assert w.is_running
            w.stop()

    def test_stop_clears_running(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback)
        with patch("flask_brain.watcher.Observer") as MockObserver:
            mock_obs = MagicMock()
            MockObserver.return_value = mock_obs
            w.start()
            w.stop()
            assert not w.is_running

    def test_stop_calls_observer_stop(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback)
        with patch("flask_brain.watcher.Observer") as MockObserver:
            mock_obs = MagicMock()
            MockObserver.return_value = mock_obs
            w.start()
            w.stop()
            mock_obs.stop.assert_called_once()

    def test_double_start_is_idempotent(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback)
        with patch("flask_brain.watcher.Observer") as MockObserver:
            w.start()
            w.start()  # second call should be a no-op
            assert MockObserver.call_count == 1
            w.stop()

    def test_stop_before_start_is_safe(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback)
        w.stop()  # must not raise
        assert not w.is_running


# ── Change Detection ───────────────────────────────────────────────────────────

class TestProjectWatcherOnChange:

    def test_py_file_change_triggers_callback(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback, debounce=0.05)
        evt = _make_event(str(project_dir / "app.py"))
        w._on_change(evt)
        time.sleep(0.2)
        callback.assert_called_once()

    def test_non_py_file_ignored(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback, debounce=0.05)
        evt = _make_event(str(project_dir / "styles.css"))
        w._on_change(evt)
        time.sleep(0.2)
        callback.assert_not_called()

    def test_directory_event_ignored(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback, debounce=0.05)
        evt = _make_event(str(project_dir / "subdir"), is_directory=True)
        w._on_change(evt)
        time.sleep(0.2)
        callback.assert_not_called()

    def test_rapid_events_coalesced(self, project_dir, callback):
        """10 rapid events should fire callback only once after debounce."""
        w = ProjectWatcher(project_dir, callback, debounce=0.1)
        for _ in range(10):
            evt = _make_event(str(project_dir / "app.py"))
            w._on_change(evt)
            time.sleep(0.01)
        time.sleep(0.3)
        callback.assert_called_once()

    def test_callback_receives_changed_path(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback, debounce=0.05)
        changed = str(project_dir / "models.py")
        evt = _make_event(changed)
        w._on_change(evt)
        time.sleep(0.2)
        callback.assert_called_once_with(changed)

    def test_excluded_venv_ignored(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback, debounce=0.05)
        evt = _make_event(str(project_dir / ".venv" / "lib" / "foo.py"))
        w._on_change(evt)
        time.sleep(0.2)
        callback.assert_not_called()

    def test_excluded_pycache_ignored(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback, debounce=0.05)
        evt = _make_event(str(project_dir / "__pycache__" / "app.cpython-311.pyc"))
        w._on_change(evt)
        time.sleep(0.2)
        callback.assert_not_called()

    def test_excluded_node_modules_ignored(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback, debounce=0.05)
        evt = _make_event(str(project_dir / "node_modules" / "foo.py"))
        w._on_change(evt)
        time.sleep(0.2)
        callback.assert_not_called()

    def test_excluded_migrations_ignored(self, project_dir, callback):
        w = ProjectWatcher(project_dir, callback, debounce=0.05)
        evt = _make_event(str(project_dir / "migrations" / "versions" / "001.py"))
        w._on_change(evt)
        time.sleep(0.2)
        callback.assert_not_called()

    def test_two_separate_bursts_fire_twice(self, project_dir, callback):
        """Two bursts separated by > debounce should fire callback twice."""
        w = ProjectWatcher(project_dir, callback, debounce=0.08)
        # First burst
        w._on_change(_make_event(str(project_dir / "app.py")))
        time.sleep(0.25)
        # Second burst
        w._on_change(_make_event(str(project_dir / "models.py")))
        time.sleep(0.25)
        assert callback.call_count == 2
