"""
Windows Startup Manager for Screen Time Tracker.
Manages auto-start via Windows Registry.
"""
import sys
import os
import winreg


APP_NAME = "ScreenTimeTracker"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_install_dir():
    """Get the standard install directory."""
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                        "ScreenTimeTracker")


def get_exe_path():
    """Get the path of the current executable."""
    if getattr(sys, 'frozen', False):
        return sys.executable
    return sys.executable


def get_installed_exe_path():
    """Get the path where the exe should be after installation."""
    return os.path.join(get_install_dir(), "ScreenTimeTracker.exe")


def is_startup_enabled():
    """Check if the app is set to start at Windows startup."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def enable_startup():
    """Enable auto-start at Windows startup."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        # Use installed path if it exists, otherwise current exe
        exe = get_installed_exe_path()
        if not os.path.exists(exe):
            exe = get_exe_path()
        # Add --minimized flag so it starts in tray
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}" --minimized')
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Failed to enable startup: {e}")
        return False


def disable_startup():
    """Disable auto-start at Windows startup."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        print(f"Failed to disable startup: {e}")
        return False


def toggle_startup():
    """Toggle startup state."""
    if is_startup_enabled():
        return disable_startup(), False
    else:
        return enable_startup(), True
