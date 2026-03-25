from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DOWNLOADS = PROJECT_ROOT / "static" / "downloads"
BUILD_ROOT = PROJECT_ROOT / "build" / "desktop-bundles"

INCLUDE_FILES = [
    "app.py",
    "account_service.py",
    "vehicle_api.py",
    "carvana_payout.py",
    "software_chat.py",
    "requirements.txt",
    "desktop_launcher.py",
]

INCLUDE_DIRS = [
    "comp_engine",
    "migrations",
    "templates",
    "static",
    "scripts",
]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "downloads"))


def prepare_bundle(target: Path, platform_name: str) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    for relative in INCLUDE_FILES:
        src = PROJECT_ROOT / relative
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    for relative in INCLUDE_DIRS:
        copy_tree(PROJECT_ROOT / relative, target / relative)

    write_text(target / "data" / ".gitkeep", "")

    write_text(
        target / "README-LOCAL.txt",
        (
            "Drive and Comp Local Software\n\n"
            "1. Extract this folder.\n"
            "2. Double-click the launcher for your platform.\n"
            "3. First launch installs local Python dependencies if needed.\n"
            "4. Your browser opens the local software automatically.\n"
        ),
    )

    if platform_name == "mac":
        write_text(
            target / "Launch Drive and Comp.command",
            "#!/bin/bash\ncd \"$(dirname \"$0\")\"\npython3 desktop_launcher.py\n",
        )
    else:
        write_text(
            target / "Launch Drive and Comp.bat",
            "@echo off\r\ncd /d %~dp0\r\npy -3 desktop_launcher.py\r\nif %ERRORLEVEL% NEQ 0 python desktop_launcher.py\r\n",
        )


def zip_bundle(source_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in source_dir.rglob("*"):
            archive.write(file_path, file_path.relative_to(source_dir.parent))


def main() -> None:
    mac_dir = BUILD_ROOT / "drive-and-comp-mac"
    windows_dir = BUILD_ROOT / "drive-and-comp-windows"
    prepare_bundle(mac_dir, "mac")
    prepare_bundle(windows_dir, "windows")
    zip_bundle(mac_dir, STATIC_DOWNLOADS / "drive-and-comp-mac.zip")
    zip_bundle(windows_dir, STATIC_DOWNLOADS / "drive-and-comp-windows.zip")
    print("Desktop bundles generated.")


if __name__ == "__main__":
    main()
