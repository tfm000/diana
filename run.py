#!/usr/bin/env python3
"""Cross-platform launcher for the Diana dashboard."""

import subprocess
import sys
from pathlib import Path


def main():
    app_path = Path(__file__).parent / "diana" / "dashboard" / "app.py"

    if not app_path.exists():
        print(f"Error: {app_path} not found")
        sys.exit(1)

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
