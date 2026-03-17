#!/usr/bin/env python3
"""Cross-platform launcher for the Diana dashboard."""

import subprocess
import sys
from pathlib import Path


def _sync_config_toml() -> None:
    """Write .streamlit/config.toml with theme and upload size from config."""
    from diana.config import get_config
    from diana.utils import detect_device_theme

    config = get_config()
    base = detect_device_theme() if config.dashboard.theme == "device" else config.dashboard.theme

    config_dir = Path(".streamlit")
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.toml").write_text(
        "[client]\n"
        'toolbarMode = "minimal"\n'
        "\n"
        "[browser]\n"
        "gatherUsageStats = false\n"
        "\n"
        "[server]\n"
        "headless = true\n"
        f"maxUploadSize = {config.dashboard.max_upload_mb}\n"
        "\n"
        "[theme]\n"
        'font = "serif"\n'
        f'base = "{base}"\n'
    )


def main():
    app_path = Path(__file__).parent / "diana" / "dashboard" / "Home.py"

    if not app_path.exists():
        print(f"Error: {app_path} not found")
        sys.exit(1)

    _sync_config_toml()

    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.port", "8501",
        "--server.headless", "false",
    ]

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nDiana stopped.")
    except FileNotFoundError:
        print("Error: streamlit not found. Install dependencies with:")
        print(f"  {sys.executable} -m pip install -r requirements.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
