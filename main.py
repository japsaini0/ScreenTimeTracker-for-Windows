"""
Screen Time Tracker - Main entry point.
A lightweight Windows app for tracking screen time with smart app detection.
"""
import sys
import os

# Ensure high DPI scaling
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from database import Database
from tracker import TrackerThread
from ui import MainWindow, create_icon


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Screen Time Tracker")
    app.setOrganizationName("SOT")
    app.setWindowIcon(create_icon())
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

    # Initialize database
    db = Database()

    # Start background tracker
    tracker = TrackerThread(db, poll_interval=3)
    tracker.start()

    # Create main window
    window = MainWindow(db, tracker)

    # Check if launched with --minimized (startup mode)
    if "--minimized" in sys.argv:
        window.hide()
    else:
        window.show()

    exit_code = app.exec()

    # Cleanup
    tracker.stop()
    db.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
