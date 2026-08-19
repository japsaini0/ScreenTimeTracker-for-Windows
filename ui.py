"""
Screen Time Tracker - Beautiful Dark UI with PySide6.
"""
import time as _time

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QSystemTrayIcon, QMenu,
    QGraphicsDropShadowEffect, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor, QIcon, QPainter, QLinearGradient, QPainterPath, QPixmap, QAction
from datetime import date, timedelta
from smart_detect import CATEGORY_COLORS, get_category_color
from startup import is_startup_enabled, toggle_startup


STYLE = """
* { font-family: 'Segoe UI', 'Inter', sans-serif; }
QMainWindow { background: #0d1117; }
QWidget#central { background: #0d1117; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: #161b22; width: 8px; margin: 0;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #30363d; min-height: 30px; border-radius: 4px;
}
QScrollBar::handle:vertical:hover { background: #484f58; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def format_time(seconds):
    """Format seconds into human-readable string."""
    if seconds < 60:
        return f"{int(seconds)}s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def format_time_full(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def create_icon():
    """Create a simple clock icon for the app."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, 64, 64)
    grad.setColorAt(0, QColor("#7C3AED"))
    grad.setColorAt(1, QColor("#2563EB"))
    p.setBrush(grad)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 14, 14)
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI", 28, QFont.Bold))
    p.drawText(pixmap.rect(), Qt.AlignCenter, "⏱")
    p.end()
    return QIcon(pixmap)


class GlowCard(QFrame):
    """A card widget with glassmorphism effect."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            GlowCard {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(22,27,34,230), stop:1 rgba(13,17,23,240));
                border: 1px solid rgba(48,54,61,0.8);
                border-radius: 16px;
                padding: 20px;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)


class AppRow(QFrame):
    """A single app entry in the breakdown list."""
    def __init__(self, name, seconds, total_seconds, category, sessions=None, parent=None):
        super().__init__(parent)
        self.expanded = False
        self.sessions = sessions or []
        self.detail_widget = None

        pct = (seconds / total_seconds * 100) if total_seconds > 0 else 0
        color = get_category_color(category)

        self.setStyleSheet(f"""
            AppRow {{
                background: rgba(22,27,34,200);
                border: 1px solid rgba(48,54,61,0.6);
                border-radius: 12px;
                padding: 12px 16px;
            }}
            AppRow:hover {{
                background: rgba(30,37,46,220);
                border: 1px solid {color}40;
            }}
        """)
        self.setCursor(Qt.PointingHandCursor)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top row
        top = QHBoxLayout()
        top.setSpacing(12)

        # Color dot
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 10px; border:none; background:transparent;")
        dot.setFixedWidth(16)
        top.addWidget(dot)

        # App name
        lbl = QLabel(name)
        lbl.setStyleSheet("color: #e6edf3; font-size: 14px; font-weight: 600; border:none; background:transparent;")
        top.addWidget(lbl, 1)

        # Category badge
        badge = QLabel(category)
        badge.setStyleSheet(f"""
            color: {color}; background: {color}18;
            border: 1px solid {color}30; border-radius: 8px;
            padding: 2px 10px; font-size: 11px;
        """)
        top.addWidget(badge)

        # Time
        time_lbl = QLabel(format_time(seconds))
        time_lbl.setStyleSheet("color: #8b949e; font-size: 14px; font-weight: 500; border:none; background:transparent;")
        top.addWidget(time_lbl)

        # Arrow
        self.arrow = QLabel("▾")
        self.arrow.setStyleSheet("color: #484f58; font-size: 12px; border:none; background:transparent;")
        self.arrow.setFixedWidth(16)
        top.addWidget(self.arrow)

        main_layout.addLayout(top)

        # Progress bar
        bar_bg = QFrame()
        bar_bg.setFixedHeight(4)
        bar_bg.setStyleSheet("background: rgba(48,54,61,0.5); border-radius: 2px; border:none;")
        bar_layout = QHBoxLayout(bar_bg)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        bar_fill = QFrame()
        bar_fill.setFixedHeight(4)
        w = max(int(pct * 2.5), 2)
        bar_fill.setFixedWidth(min(w, 250))
        bar_fill.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {color}, stop:1 {color}80);
            border-radius: 2px; border:none;
        """)
        bar_layout.addWidget(bar_fill)
        bar_layout.addStretch()

        pct_label = QLabel(f"{pct:.1f}%")
        pct_label.setStyleSheet("color: #484f58; font-size: 11px; border:none; background:transparent;")
        pct_label.setFixedWidth(45)
        pct_label.setAlignment(Qt.AlignRight)

        bar_outer = QHBoxLayout()
        bar_outer.setContentsMargins(28, 6, 0, 0)
        bar_outer.addWidget(bar_bg, 1)
        bar_outer.addWidget(pct_label)
        main_layout.addLayout(bar_outer)

        # Detail section (hidden by default)
        self.detail_widget = QWidget()
        self.detail_widget.setVisible(False)
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(28, 8, 0, 4)
        detail_layout.setSpacing(4)

        if self.sessions:
            for s in self.sessions[:15]:
                row = QHBoxLayout()
                t_lbl = QLabel(s.get("title", "")[:60])
                t_lbl.setStyleSheet("color: #8b949e; font-size: 12px; border:none; background:transparent;")
                row.addWidget(t_lbl, 1)
                dur = QLabel(format_time_full(s.get("duration", 0)))
                dur.setStyleSheet("color: #58a6ff; font-size: 12px; border:none; background:transparent;")
                row.addWidget(dur)
                time_range = QLabel(f"{s.get('start','')} – {s.get('end','')}")
                time_range.setStyleSheet("color: #484f58; font-size: 11px; border:none; background:transparent;")
                time_range.setFixedWidth(130)
                row.addWidget(time_range)
                detail_layout.addLayout(row)
        else:
            no_data = QLabel("No session details available")
            no_data.setStyleSheet("color: #484f58; font-size: 12px; font-style: italic; border:none; background:transparent;")
            detail_layout.addWidget(no_data)

        main_layout.addWidget(self.detail_widget)

    def mousePressEvent(self, event):
        self.expanded = not self.expanded
        self.detail_widget.setVisible(self.expanded)
        self.arrow.setText("▴" if self.expanded else "▾")
        super().mousePressEvent(event)


class WeeklyChart(QWidget):
    """Simple bar chart for weekly data."""
    def __init__(self, weekly_data, parent=None):
        super().__init__(parent)
        self.data = weekly_data
        self.setFixedHeight(140)
        self.setMinimumWidth(300)

    def paintEvent(self, event):
        if not self.data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        max_val = max((d["seconds"] for d in self.data), default=1) or 1
        bar_w = min(36, (w - 60) // 7)
        spacing = (w - bar_w * 7) // 8
        chart_h = h - 30

        today_idx = len(self.data) - 1

        for i, d in enumerate(self.data):
            x = spacing + i * (bar_w + spacing)
            bar_h = max(int((d["seconds"] / max_val) * (chart_h - 10)), 4)
            y = chart_h - bar_h

            # Bar gradient
            grad = QLinearGradient(x, y, x, chart_h)
            if i == today_idx:
                grad.setColorAt(0, QColor("#7C3AED"))
                grad.setColorAt(1, QColor("#2563EB"))
            else:
                grad.setColorAt(0, QColor("#30363d"))
                grad.setColorAt(1, QColor("#21262d"))

            path = QPainterPath()
            path.addRoundedRect(x, y, bar_w, bar_h, 6, 6)
            p.fillPath(path, grad)

            # Day label
            p.setPen(QColor("#8b949e" if i != today_idx else "#e6edf3"))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(x, h - 4, bar_w, 14, Qt.AlignCenter, d["day"])

            # Time label on top
            if d["seconds"] > 0:
                p.setPen(QColor("#8b949e"))
                p.setFont(QFont("Segoe UI", 8))
                p.drawText(x - 10, y - 14, bar_w + 20, 14, Qt.AlignCenter, format_time(d["seconds"]))

        p.end()


class MainWindow(QMainWindow):
    def __init__(self, db, tracker):
        super().__init__()
        self.db = db
        self.tracker = tracker
        self.selected_date = date.today()

        # Live counter state
        self._last_db_total = 0.0
        self._current_app_name = ""
        self._current_app_start = 0.0

        self.setWindowTitle("Screen Time Tracker")
        self.setMinimumSize(480, 700)
        self.resize(520, 800)
        self.setWindowIcon(create_icon())
        self.setStyleSheet(STYLE)

        self._setup_tray()
        self._build_ui()

        # Full data refresh every 15 seconds (rebuilds breakdown list)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(15000)

        # LIVE 1-second tick for the total counter (lightweight, no DB)
        self.live_timer = QTimer()
        self.live_timer.timeout.connect(self._tick_live)
        self.live_timer.start(1000)

        tracker.data_updated.connect(self._on_data_updated)
        tracker.current_app_changed.connect(self._on_app_changed)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(create_icon(), self)
        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)
        menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.setToolTip("Screen Time Tracker")
        self.tray.show()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Screen Time")
        title.setStyleSheet("""
            color: #e6edf3; font-size: 26px; font-weight: 700;
            background: transparent;
        """)
        header.addWidget(title)
        header.addStretch()

        # Startup toggle
        self.startup_btn = QPushButton("⚡ Startup: " + ("ON" if is_startup_enabled() else "OFF"))
        self.startup_btn.setStyleSheet("""
            QPushButton {
                color: #8b949e; background: rgba(48,54,61,0.5);
                border: 1px solid #30363d; border-radius: 8px;
                padding: 6px 14px; font-size: 12px;
            }
            QPushButton:hover { background: rgba(48,54,61,0.8); color: #e6edf3; }
        """)
        self.startup_btn.setCursor(Qt.PointingHandCursor)
        self.startup_btn.clicked.connect(self._toggle_startup)
        header.addWidget(self.startup_btn)
        layout.addLayout(header)

        # Date navigation
        date_nav = QHBoxLayout()
        self.prev_btn = QPushButton("◀")
        self.next_btn = QPushButton("▶")
        self.today_btn = QPushButton("Today")
        for btn in [self.prev_btn, self.next_btn, self.today_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    color: #8b949e; background: transparent;
                    border: 1px solid #30363d; border-radius: 8px;
                    padding: 6px 12px; font-size: 13px;
                }
                QPushButton:hover { background: rgba(48,54,61,0.5); color: #e6edf3; }
            """)
            btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.clicked.connect(lambda: self._change_date(-1))
        self.next_btn.clicked.connect(lambda: self._change_date(1))
        self.today_btn.clicked.connect(self._go_today)

        self.date_label = QLabel()
        self.date_label.setStyleSheet("color: #8b949e; font-size: 14px; background:transparent;")
        self.date_label.setAlignment(Qt.AlignCenter)

        date_nav.addWidget(self.prev_btn)
        date_nav.addStretch()
        date_nav.addWidget(self.date_label)
        date_nav.addStretch()
        date_nav.addWidget(self.today_btn)
        date_nav.addWidget(self.next_btn)
        layout.addLayout(date_nav)

        # Total time card
        self.total_card = GlowCard()
        tc_layout = QVBoxLayout(self.total_card)
        tc_layout.setSpacing(4)
        tc_top = QLabel("TOTAL SCREEN TIME")
        tc_top.setStyleSheet("color: #8b949e; font-size: 11px; letter-spacing: 2px; border:none; background:transparent;")
        tc_layout.addWidget(tc_top)
        self.total_label = QLabel("0h 0m")
        self.total_label.setStyleSheet("""
            color: transparent; font-size: 48px; font-weight: 800;
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #7C3AED, stop:0.5 #2563EB, stop:1 #06B6D4);
            -webkit-background-clip: text; background-clip: text;
            border: none;
        """)
        # Fallback since Qt doesn't support background-clip
        self.total_label.setStyleSheet("color: #c4b5fd; font-size: 48px; font-weight: 800; border:none; background:transparent;")
        tc_layout.addWidget(self.total_label)

        self.current_app_label = QLabel("Tracking...")
        self.current_app_label.setStyleSheet("color: #58a6ff; font-size: 12px; border:none; background:transparent;")
        tc_layout.addWidget(self.current_app_label)
        layout.addWidget(self.total_card)

        # Weekly chart card
        self.chart_card = GlowCard()
        chart_layout = QVBoxLayout(self.chart_card)
        chart_title = QLabel("THIS WEEK")
        chart_title.setStyleSheet("color: #8b949e; font-size: 11px; letter-spacing: 2px; border:none; background:transparent;")
        chart_layout.addWidget(chart_title)
        self.chart_container = QVBoxLayout()
        chart_layout.addLayout(self.chart_container)
        layout.addWidget(self.chart_card)

        # App breakdown header
        breakdown_header = QHBoxLayout()
        bh_label = QLabel("APP BREAKDOWN")
        bh_label.setStyleSheet("color: #8b949e; font-size: 11px; letter-spacing: 2px; background:transparent;")
        breakdown_header.addWidget(bh_label)
        breakdown_header.addStretch()
        self.app_count_label = QLabel("")
        self.app_count_label.setStyleSheet("color: #484f58; font-size: 11px; background:transparent;")
        breakdown_header.addWidget(self.app_count_label)
        layout.addLayout(breakdown_header)

        # Scrollable app list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.app_list_widget = QWidget()
        self.app_list_widget.setStyleSheet("background: transparent;")
        self.app_list_layout = QVBoxLayout(self.app_list_widget)
        self.app_list_layout.setSpacing(8)
        self.app_list_layout.setContentsMargins(0, 0, 4, 0)
        self.app_list_layout.addStretch()
        scroll.setWidget(self.app_list_widget)
        layout.addWidget(scroll, 1)

        self.refresh_data()

    def _tick_live(self):
        """Called every 1 second — updates the total counter live without DB."""
        if self.selected_date != date.today():
            return  # Only tick on today's view

        # Compute live total = last DB snapshot + ongoing session elapsed
        total = self.tracker.last_db_total
        if self.tracker.session_start_time > 0:
            elapsed = _time.time() - self.tracker.session_start_time
            total += elapsed

        self.total_label.setText(format_time_full(total) if total > 0 else "0h 0m")
        self.tray.setToolTip(f"Screen Time: {format_time(total)}")

        # Update current app line with live duration
        if self._current_app_name and self._current_app_start > 0:
            app_elapsed = _time.time() - self._current_app_start
            self.current_app_label.setText(
                f"Currently: {self._current_app_name}  •  {format_time_full(app_elapsed)}"
            )

    def refresh_data(self):
        date_str = self.selected_date.isoformat()
        self.date_label.setText(self.selected_date.strftime("%A, %B %d, %Y"))

        is_today = self.selected_date == date.today()
        self.next_btn.setEnabled(not is_today)

        # Total
        total = self.db.get_daily_total(date_str)
        self._last_db_total = total
        self.total_label.setText(format_time_full(total) if total > 0 else "0h 0m")
        self.tray.setToolTip(f"Screen Time: {format_time(total)}")

        # Weekly chart
        while self.chart_container.count():
            w = self.chart_container.takeAt(0).widget()
            if w:
                w.deleteLater()
        weekly = self.db.get_weekly_data()
        chart = WeeklyChart(weekly)
        self.chart_container.addWidget(chart)

        # App breakdown
        breakdown = self.db.get_daily_breakdown(date_str)
        self.app_count_label.setText(f"{len(breakdown)} apps")

        # Clear old rows
        while self.app_list_layout.count() > 1:
            item = self.app_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not breakdown:
            empty = QLabel("No screen time recorded" if not is_today else "Start using your laptop to see tracking data")
            empty.setStyleSheet("color: #484f58; font-size: 13px; padding: 30px; background:transparent;")
            empty.setAlignment(Qt.AlignCenter)
            self.app_list_layout.insertWidget(0, empty)
        else:
            for i, app in enumerate(breakdown):
                sessions = self.db.get_app_sessions(date_str, app["name"])
                row = AppRow(app["name"], app["seconds"], total, app["category"], sessions)
                self.app_list_layout.insertWidget(i, row)

    def _on_data_updated(self):
        if self.selected_date == date.today():
            self.refresh_data()

    def _on_app_changed(self, name, category):
        self._current_app_name = name
        self._current_app_start = _time.time()
        self.current_app_label.setText(f"Currently: {name}")

    def _change_date(self, delta):
        self.selected_date += timedelta(days=delta)
        if self.selected_date > date.today():
            self.selected_date = date.today()
        self.refresh_data()

    def _go_today(self):
        self.selected_date = date.today()
        self.refresh_data()

    def _toggle_startup(self):
        success, enabled = toggle_startup()
        if success:
            self.startup_btn.setText("⚡ Startup: " + ("ON" if enabled else "OFF"))

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._show_window()

    def _show_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit(self):
        self.tracker.stop()
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Screen Time Tracker",
            "Running in background. Click tray icon to open.",
            QSystemTrayIcon.Information, 2000
        )
