from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from comp_engine.config import EngineConfig
from comp_engine.storage import SQLiteRepository


def main() -> None:
    config = EngineConfig.from_env()
    SQLiteRepository(config.sqlite_path)
    print(f"Migrations applied to {config.sqlite_path}")


if __name__ == "__main__":
    main()
