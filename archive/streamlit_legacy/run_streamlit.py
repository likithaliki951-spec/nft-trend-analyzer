"""Start Streamlit on the port assigned by the Replit artifact service."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def main() -> None:
    project_root = Path(__file__).resolve().parent
    app_file = project_root / "app.py"
    port = os.environ.get("PORT", "5000")
    if not port.isdigit() or not 0 < int(port) < 65536:
        raise ValueError(f"Invalid PORT value: {port!r}")
    if not app_file.is_file():
        raise FileNotFoundError(f"Streamlit entrypoint not found: {app_file}")

    os.chdir(project_root)
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_file),
        "--server.address",
        "0.0.0.0",
        "--server.port",
        port,
        "--server.headless",
        "true",
        "--server.enableCORS",
        "false",
        "--server.enableWebsocketCompression",
        "false",
    ]
    os.execvpe(sys.executable, command, os.environ.copy())


if __name__ == "__main__":
    main()
