"""
Screen Time Tracker - Background tracking engine.
Polls the active window every 3 seconds to minimize CPU usage.

Optimized:
- No DB commit on every poll (batched writes)
- Throttled summary rebuilds
- Throttled signal emissions to prevent duplicate UI refreshes
"""
import time
import ctypes
import ctypes.wintypes
from datetime import date
from PySide6.QtCore import QThread, Signal

from smart_detect import detect_app
from database import Database


# Windows API setup
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi


def get_active_window_info():
    """Get the currently active window's process name and title."""
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None, None

        # Get window title
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return None, None
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        # Get process ID
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # Get process name
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        process_handle = kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value
        )
        if not process_handle:
            return None, title

        try:
            exe_buf = ctypes.create_unicode_buffer(512)
            psapi.GetModuleFileNameExW(process_handle, None, exe_buf, 512)
            exe_path = exe_buf.value
            process_name = exe_path.split("\\")[-1] if exe_path else None
        finally:
            kernel32.CloseHandle(process_handle)

        return process_name, title

    except Exception:
        return None, None


class TrackerThread(QThread):
    """Background thread that polls the active window."""

    # Signals to communicate with UI
    data_updated = Signal()  # Emitted when data changes
    current_app_changed = Signal(str, str)  # (display_name, category)

    def __init__(self, db: Database, poll_interval=3):
        super().__init__()
        self.db = db
        self.poll_interval = poll_interval
        self._running = True

        self._current_session_id = None
        self._current_display_name = None
        self._current_category = None
        self._current_date = date.today().isoformat()
        self._last_summary_update = 0
        self._last_flush_time = 0
        self._summary_interval = 30    # Rebuild summary every 30s (was 15s)
        self._flush_interval = 15      # Flush pending writes every 15s

        # Exposed for live UI updates (read-only from UI thread)
        self.session_start_time = 0.0  # timestamp when current session began
        self.last_db_total = 0.0       # last known total from DB summary

    def run(self):
        """Main tracking loop."""
        while self._running:
            try:
                self._poll()
            except Exception as e:
                print(f"Tracker error: {e}")
            time.sleep(self.poll_interval)

    def _poll(self):
        """Poll the active window and update tracking."""
        process_name, window_title = get_active_window_info()

        if not process_name or not window_title:
            # Screen might be locked or no active window
            self._end_current_session()
            return

        # Skip our own app
        if "screen time" in (window_title or "").lower():
            return

        # Detect the actual app/website
        display_name, category = detect_app(process_name, window_title)

        # Check if date changed (midnight rollover)
        today = date.today().isoformat()
        if today != self._current_date:
            self._end_current_session()
            self._current_date = today

        # Check if the app changed
        if display_name != self._current_display_name:
            self._end_current_session()
            self._start_new_session(process_name, display_name, window_title, category)
        else:
            # Same app — update duration in DB (no commit, stays in WAL)
            if self._current_session_id:
                self.db.update_session_duration(self._current_session_id)

        # Periodically flush pending writes to disk
        now = time.time()
        if now - self._last_flush_time >= self._flush_interval:
            self.db.flush()
            self._last_flush_time = now

        # Periodically rebuild daily summary (less frequently)
        if now - self._last_summary_update >= self._summary_interval:
            self.db.rebuild_daily_summary(self._current_date)
            self.last_db_total = self.db.get_daily_total(self._current_date)
            self._last_summary_update = now
            self.data_updated.emit()

    def _start_new_session(self, process_name, display_name, window_title, category):
        """Start tracking a new app session."""
        self._current_display_name = display_name
        self._current_category = category
        self.session_start_time = time.time()
        self._current_session_id = self.db.start_session(
            process_name, display_name, window_title, category
        )
        self.current_app_changed.emit(display_name, category)

    def _end_current_session(self):
        """End the current tracking session."""
        if self._current_session_id:
            self.db.end_session(self._current_session_id)
            # Rebuild summary only on session end (important for accuracy)
            self.db.rebuild_daily_summary(self._current_date)
            self.last_db_total = self.db.get_daily_total(self._current_date)
            self.session_start_time = 0.0
            self._current_session_id = None
            self._current_display_name = None
            self._current_category = None
            self.data_updated.emit()

    def stop(self):
        """Stop the tracker thread."""
        self._running = False
        self._end_current_session()
        self.wait(5000)
