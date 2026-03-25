from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
RUNTIME_DIR = PROJECT_ROOT / ".runtime"
VENV_DIR = RUNTIME_DIR / "venv"
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = RUNTIME_DIR / "logs"
APP_NAME = "DriveAndComp"


def load_local_environment() -> None:
    app_support_dir = Path.home() / "Library" / "Application Support" / APP_NAME
    candidate_files = [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / "drive-and-comp.env",
        app_support_dir / ".env",
        app_support_dir / "drive-and-comp.env",
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


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python3"


def ensure_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def run_command(args: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=PROJECT_ROOT, check=True, env=env or os.environ.copy())


def ensure_venv() -> Path:
    python_path = venv_python()
    if python_path.exists():
        return python_path
    run_command([sys.executable, "-m", "venv", str(VENV_DIR)])
    python_path = venv_python()
    run_command([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
    run_command([str(python_path), "-m", "pip", "install", "-r", str(PROJECT_ROOT / "requirements.txt")])
    return python_path


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(url: str, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("Local software did not start in time.")


def main() -> None:
    load_local_environment()
    ensure_dirs()
    python_path = ensure_venv()
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["FLASK_DEBUG"] = "false"
    env["SESSION_COOKIE_SECURE"] = "false"
    env["CANONICAL_HOST"] = ""
    env["PUBLIC_BASE_URL"] = base_url
    env["COMP_SQLITE_PATH"] = str(DATA_DIR / "vehicle_comps.db")

    run_command([str(python_path), str(PROJECT_ROOT / "scripts" / "migrate.py")], env=env)

    stdout_log = (LOG_DIR / "app.stdout.log").open("a", encoding="utf-8")
    stderr_log = (LOG_DIR / "app.stderr.log").open("a", encoding="utf-8")
    process = subprocess.Popen(
        [str(python_path), str(PROJECT_ROOT / "app.py")],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=stdout_log,
        stderr=stderr_log,
    )

    try:
        wait_for_server(f"{base_url}/healthz")
        webbrowser.open(base_url)
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
    except Exception:
        process.terminate()
        raise


if __name__ == "__main__":
    main()
