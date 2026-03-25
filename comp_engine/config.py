from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(root: Path | None = None) -> None:
    project_root = root or Path(__file__).resolve().parents[1]
    dotenv_path = project_root / ".env"
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(slots=True)
class EngineConfig:
    cache_ttl_seconds: int
    http_timeout_seconds: int
    http_retry_count: int
    max_source_workers: int
    max_source_results: int
    max_detail_enrichment: int
    max_vin_decodes: int
    sqlite_path: Path
    enable_craigslist: bool
    enable_autodev: bool
    enable_oneauto: bool
    enable_ebay_motors: bool
    enable_marketcheck_dealer: bool
    enable_marketcheck_private: bool
    enable_marketcheck: bool
    enable_manual_import: bool
    enable_custom_source: bool
    ebay_client_id: str
    ebay_client_secret: str
    ebay_scope: str
    ebay_marketplace_id: str
    autodev_api_key: str
    oneauto_api_key: str
    marketcheck_api_key: str

    @classmethod
    def from_env(cls, root: Path | None = None) -> "EngineConfig":
        project_root = root or Path(__file__).resolve().parents[1]
        _load_dotenv(project_root)
        default_db = project_root / "data" / "vehicle_comps.db"
        configured_db = Path(os.getenv("COMP_SQLITE_PATH", str(default_db)))
        sqlite_path = configured_db if configured_db.is_absolute() else (project_root / configured_db).resolve()
        autodev_api_key = os.getenv("AUTODEV_API_KEY", "").strip()
        oneauto_api_key = os.getenv("ONEAUTO_API_KEY", "").strip()
        ebay_client_id = os.getenv("EBAY_CLIENT_ID", "").strip()
        ebay_client_secret = os.getenv("EBAY_CLIENT_SECRET", "").strip()
        marketcheck_api_key = os.getenv("MARKETCHECK_API_KEY", "").strip()
        marketcheck_enabled = _env_flag("COMP_ENABLE_MARKETCHECK", False) and bool(marketcheck_api_key)
        return cls(
            cache_ttl_seconds=_env_int("COMP_CACHE_TTL_SECONDS", 1800),
            http_timeout_seconds=_env_int("COMP_HTTP_TIMEOUT_SECONDS", 20),
            http_retry_count=_env_int("COMP_HTTP_RETRY_COUNT", 2),
            max_source_workers=_env_int("COMP_MAX_SOURCE_WORKERS", 6),
            max_source_results=_env_int("COMP_MAX_SOURCE_RESULTS", 80),
            max_detail_enrichment=_env_int("COMP_MAX_DETAIL_ENRICHMENT", 18),
            max_vin_decodes=_env_int("COMP_MAX_VIN_DECODES", 24),
            sqlite_path=sqlite_path,
            enable_craigslist=_env_flag("COMP_ENABLE_CRAIGSLIST", True),
            enable_autodev=_env_flag("COMP_ENABLE_AUTODEV", bool(autodev_api_key)),
            enable_oneauto=_env_flag("COMP_ENABLE_ONEAUTO", bool(oneauto_api_key)),
            enable_ebay_motors=_env_flag("COMP_ENABLE_EBAY_MOTORS", bool(ebay_client_id and ebay_client_secret)),
            enable_marketcheck=marketcheck_enabled,
            enable_marketcheck_dealer=_env_flag("COMP_ENABLE_MARKETCHECK_DEALER", marketcheck_enabled),
            enable_marketcheck_private=_env_flag("COMP_ENABLE_MARKETCHECK_PRIVATE", False),
            enable_manual_import=_env_flag("COMP_ENABLE_MANUAL_IMPORT", True),
            enable_custom_source=_env_flag("COMP_ENABLE_CUSTOM_SOURCE", True),
            ebay_client_id=ebay_client_id,
            ebay_client_secret=ebay_client_secret,
            ebay_scope=os.getenv(
                "EBAY_SCOPE",
                "https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/buy.item.feed",
            ).strip(),
            ebay_marketplace_id=os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US").strip(),
            autodev_api_key=autodev_api_key,
            oneauto_api_key=oneauto_api_key,
            marketcheck_api_key=marketcheck_api_key,
        )
