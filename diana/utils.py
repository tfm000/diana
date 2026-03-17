"""Shared utilities for Diana."""

import platform
import subprocess


def detect_device_theme() -> str:
    """Detect the OS dark/light mode. Returns 'dark' or 'light'."""
    try:
        system = platform.system()
        if system == "Darwin":
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and "dark" in result.stdout.strip().lower():
                return "dark"
        elif system == "Linux":
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True, timeout=5,
            )
            if "dark" in result.stdout.strip().lower():
                return "dark"
        elif system == "Windows":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            if value == 0:
                return "dark"
    except Exception:
        pass
    return "light"
