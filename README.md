# Car Flip Analyzer

Production deployment for this app should use a hybrid setup:

- GitHub stores the code
- Render runs the Flask app, SQLite database, sessions, and background worker
- GoDaddy manages the custom domain
- Vercel is optional later for a frontend-only split, but it is not the primary runtime for the current app

## Why Render Is The Primary Host

This codebase is not a static frontend. It currently depends on:

- Flask server routes and session auth
- SQLite-backed app data
- account credits and admin tools
- an in-process Carvana payout worker
- Browser Use automation jobs

That makes Render the correct first production host for the whole app.

## Local Verification

Run this before deploying:

```bash
cd "/Users/aidenmessier/Documents/New project"
.venv/bin/python scripts/migrate.py
.venv/bin/python app.py
```

Then check:

- main app loads
- signup/login work
- individual evaluation works
- bulk evaluation works
- admin pages load
- tier/credit edits persist
- Carvana payout job can be created

## Required Environment Variables

Set these in Render, not in committed code:

Core:

- `FLASK_SECRET_KEY`
- `SESSION_COOKIE_SECURE=true`
- `COMP_SQLITE_PATH=/var/data/vehicle_comps.db`
- `CANONICAL_HOST=yourdomain.com`
- `FLASK_DEBUG=false`

LLM / automation:

- `OPENAI_API_KEY`
- `BROWSER_USE_API_KEY`
- `CARVANA_PAYOUT_ENABLED=true`

Vehicle source adapters:

- `AUTODEV_API_KEY`
- `ONEAUTO_API_KEY`
- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`
- `MARKETCHECK_API_KEY`

Optional admin/test defaults:

- `TEST_ADMIN_EMAIL`
- `TEST_ADMIN_PASSWORD`

See [`.env.example`](/Users/aidenmessier/Documents/New%20project/.env.example) for the full list.

## Render Deployment

This repo already includes [render.yaml](/Users/aidenmessier/Documents/New%20project/render.yaml).

It is configured to:

- install Python dependencies
- run the Flask app with `gunicorn`
- use a persistent disk for SQLite
- expose a health check at `/healthz`
- keep a single worker process, which matches the current in-process background worker model

### Render steps

1. Push this project to a GitHub repository.
2. In Render, create a new Blueprint or Web Service from the GitHub repo.
3. Confirm the service picks up [render.yaml](/Users/aidenmessier/Documents/New%20project/render.yaml).
4. Add all required environment variables in Render.
5. Deploy.
6. Wait for the service to come up and verify the Render URL works.

## GoDaddy Domain Setup

Recommended setup:

- `www.yourdomain.com` points to Render using the DNS record Render provides
- `yourdomain.com` is also added in Render as the apex/root domain

### Steps

1. Open the Render service.
2. Go to `Settings` or `Domains`.
3. Add:
   - `yourdomain.com`
   - `www.yourdomain.com`
4. Copy the DNS instructions Render shows.
5. In GoDaddy DNS:
   - add the required `CNAME` for `www`
   - add the required apex/root record(s) for the root domain
6. Wait for DNS to propagate.
7. Confirm SSL is issued by Render.

Set:

- `CANONICAL_HOST=yourdomain.com`

or, if you prefer `www`, set:

- `CANONICAL_HOST=www.yourdomain.com`

The app will redirect GET/HEAD traffic to that canonical host.

## GitHub Workflow

1. Create a new GitHub repo.
2. Commit the project.
3. Push the current branch.
4. Connect the repo to Render.
5. Future pushes to the connected branch will trigger redeploys.

## What Must Stay Off Vercel For Now

Do not move the current backend to Vercel in v1. The following currently need a real backend host:

- Flask API routes
- SQLite persistent storage
- session/auth handling
- in-process Carvana payout worker
- Browser Use job execution

If you later want Vercel in the stack, the right next step is:

- Vercel for a separate frontend
- Render (or another backend host) for API + worker + data

## Production Verification Checklist

After deployment, verify:

- Render URL loads
- custom domain loads
- SSL is active
- login/signup work
- account status updates correctly
- admin pages load
- tier/credit changes persist after refresh
- individual and bulk evaluations work
- Carvana payout job reaches `queued` and then updates status
- `/healthz` returns healthy

## Known First-Launch Limitations

- SQLite is acceptable for this first production launch, but it is not the long-term scaling database.
- Carvana worker is still in-process with the web app. That is fine for v1, but later it should move to a separate worker service.
- Vercel is intentionally not part of the live runtime path yet.
