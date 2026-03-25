# Graze on Main Handoff

This folder is a clean handoff version of the current Graze on Main website.

It is structured as a static site so another Codex session can:

- inspect all current pages
- edit shared styling in `assets/styles.css`
- edit shared interactions in `assets/site.js`
- edit page content directly in the HTML files
- keep all Graze image and PDF assets from `graze-source/`

## Files

- `index.html`
- `menu/index.html`
- `events/index.html`
- `club/index.html`
- `contact/index.html`
- `assets/styles.css`
- `assets/site.js`
- `graze-source/`

## Preview locally

```bash
npm start
```

Then open `http://127.0.0.1:4173/`.

You can also serve it with any static file server.
