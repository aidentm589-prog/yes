# Source Capabilities

This project uses a source-adapter architecture so each source can be enabled, disabled, tested, and replaced independently.

## Implemented Sources

| Source | Status | Official API | Fragile | Current fields | Notes |
| --- | --- | --- | --- | --- | --- |
| Craigslist | Implemented | No | Yes | title, price, URL, market, city/state, geo, images, mileage, condition, title status, transmission, fuel, body style, VIN when exposed | Uses public listing pages only. No login, no CAPTCHA bypass, no bot-evasion. Listing detail enrichment is best-effort and isolated behind the adapter. |
| auto.dev | Implemented | Yes | No | VIN, year, make, model, trim, body style, drivetrain, engine, transmission, fuel, color, price, mileage, dealer, city/state/zip, geo, image, listing age, Carfax URL | Official vehicle listings API adapter. Auto-enables when `AUTODEV_API_KEY` is configured. |
| One Auto API | Implemented | Yes | No | year, make, model, trim, body style, drivetrain, engine, transmission, fuel, price, mileage, dealer, location, images, listing age | Official One Auto inventory adapter. Auto-enables when `ONEAUTO_API_KEY` is configured. Live access depends on the One Auto account being active and billed. |
| eBay Motors | Implemented | Yes | No | title, price, URL, image, location, condition, inferred mileage, inferred trim | Uses the official eBay Browse API plus OAuth client credentials. Disabled until credentials are configured. |
| MarketCheck Dealer | Implemented | Yes | No | dealer inventory specs, VIN, mileage, price, location, images, dealer name | Official adapter for dealer listings. Disabled until `MARKETCHECK_API_KEY` is configured. |
| MarketCheck Private Party | Implemented | Yes | No | private-party specs, VIN, mileage, price, location, images | Official adapter for private-party listings. Disabled until `MARKETCHECK_API_KEY` is configured. |
| NHTSA VIN Decode | Implemented | Yes | No | VIN, year, make, model, trim, body style, drivetrain, engine, fuel, transmission | Used to normalize query input first, then decode listing VINs during comp normalization so trim/spec matching is less likely to mix vehicles like `M340i` and `330i`. |
| Manual Import | Implemented | Yes | No | CSV rows, pasted URLs, manual JSON payloads | Lets you blend trusted outside comps into the engine without changing the UI first. |
| Custom Source | Implemented | Internal | No | custom normalized payloads | Internal adapter interface for future trusted integrations. |

## Stubbed Future Sources

| Source | Status | Official API | Fragile | Notes |
| --- | --- | --- | --- | --- |
| Cars.com | Stub only | No public compliant search integration wired | Yes | Disabled placeholder only. |
| Autotrader | Stub only | No public compliant search integration wired | Yes | Disabled placeholder only. |
| CarGurus | Stub only | No public compliant search integration wired | Yes | Disabled placeholder only. |
| Facebook Marketplace | Stub only | Unsupported by default | Yes | Left disabled unless a compliant approved integration path becomes available. |

## Policy

- Prefer official APIs first.
- If a source is unofficial or brittle, isolate it behind its own adapter.
- One source failure must never break the whole comp engine.
- No CAPTCHA bypass, login circumvention, or bot-evasion logic is implemented here.
