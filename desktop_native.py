from __future__ import annotations

import os
import socket
import sys
import threading
from pathlib import Path

import webview
from werkzeug.serving import make_server


APP_NAME = "DriveAndComp"
PROJECT_ROOT = Path(__file__).resolve().parent


def bundled_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return PROJECT_ROOT


def local_app_support_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


def local_data_dir() -> Path:
    return local_app_support_dir() / "data"


DATA_DIR = local_data_dir()


def load_local_environment() -> None:
    executable_dir = Path(sys.executable).resolve().parent
    candidate_files = [
        executable_dir / ".env",
        executable_dir / "drive-and-comp.env",
        executable_dir.parent / ".env",
        executable_dir.parent / "drive-and-comp.env",
        local_app_support_dir() / ".env",
        local_app_support_dir() / "drive-and-comp.env",
        PROJECT_ROOT / ".env",
        bundled_root() / ".env",
        Path("/Users/aidenmessier/Documents/New project/.env"),
    ]
    seen: set[Path] = set()
    for candidate in candidate_files:
        try:
            resolved = candidate.resolve()
        except FileNotFoundError:
            resolved = candidate
        if resolved in seen or not candidate.exists():
            continue
        seen.add(resolved)
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def configure_environment() -> str:
    load_local_environment()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    os.environ.setdefault("PORT", str(port))
    os.environ.setdefault("FLASK_DEBUG", "false")
    os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
    os.environ["CANONICAL_HOST"] = ""
    os.environ["PUBLIC_BASE_URL"] = base_url
    os.environ.setdefault("COMP_SQLITE_PATH", str(DATA_DIR / "vehicle_comps.db"))
    return base_url


class LocalServer:
    def __init__(self, app, host: str, port: int) -> None:
        self._server = make_server(host, port, app, threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)


def main() -> None:
    base_url = configure_environment()
    from app import app as flask_app

    port = int(os.environ["PORT"])
    server = LocalServer(flask_app, "127.0.0.1", port)
    server.start()

    window = webview.create_window(
        "Drive and Comp",
        base_url,
        min_size=(1200, 760),
        text_select=True,
        background_color="#08142a",
    )

    try:
        webview.start()
    finally:
        server.stop()


if __name__ == "__main__":
    main()
