from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vehicle_api import VehicleValueService


def main() -> None:
    service = VehicleValueService()
    result = service.create_magic_login_link(
        "https://aidens-car-resell-price-analyzer.onrender.com",
    )
    print(result["url"])
    print(f"Expires: {result['expires_at']}")


if __name__ == "__main__":
    main()
