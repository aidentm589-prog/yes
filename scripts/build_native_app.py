from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"
STATIC_DOWNLOADS = PROJECT_ROOT / "static" / "downloads"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    app_name = "DriveAndComp"
    run(
        [
            str(PROJECT_ROOT / ".venv" / "bin" / "pyinstaller"),
            "--noconfirm",
            "--windowed",
            "--name",
            app_name,
            "--add-data",
            "templates:templates",
            "--add-data",
            "static:static",
            "--add-data",
            "migrations:migrations",
            "--hidden-import",
            "app",
            "--hidden-import",
            "account_service",
            "--hidden-import",
            "vehicle_api",
            "--collect-submodules",
            "comp_engine",
            "desktop_native.py",
        ]
    )

    app_path = DIST_DIR / f"{app_name}.app"
    zip_target = STATIC_DOWNLOADS / "drive-and-comp-mac-native.zip"
    if zip_target.exists():
        zip_target.unlink()
    shutil.make_archive(str(zip_target.with_suffix("")), "zip", DIST_DIR, f"{app_name}.app")
    print(f"Native macOS app bundled at {zip_target}")


if __name__ == "__main__":
    main()
