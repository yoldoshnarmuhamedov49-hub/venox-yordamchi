# Venox Yordamchi — Inline Telegram Bot Constructor

A lightning-fast Telegram bot: every feature runs through rich inline keyboards
inside Telegram. No web server, no external page, no loading screens.

## Features

- **192 templates in 16 categories** — E-commerce, Ta'lim, Kontent, AI & Utility, ChatGPT & AI, SMM, Crypto, Avtomobil, Turizm, Sug'urta, Ko'chmas mulk, O'yin, Biznes, Sog'liq, Xizmatlar, Foydali vositalar.
- **Custom bot builder** — step-by-step creation with name, welcome text, buttons and auto-reply; JSON export and bot management.
- **Custom bot request** — `/request` collects a project brief and forwards it to the admin.
- **Tiers** — Free (0 UZS), Standart (**60,000 UZS** / 30 days), Ultra Pro (150,000 UZS / 90 days).
- **Payments** — card `5614 6830 1549 1525`; the user sends a receipt screenshot, the admin approves/rejects it and the tier activates automatically.
- **Admin** — ID `8527026238` (@THE_VENOX) has permanent Ultra Pro/VIP with unlimited access, plus receipt review, broadcast and VIP grants.
- **Instant** — pure long polling; no HTTP server, no Render cold-start spinner.

## Local run

```bash
python -m pip install -r requirements.txt
cp .env.example .env        # add your BOT_TOKEN
python bot.py
```

The token is read from the environment or a local `.env` file; it is never
committed.

## Commands

`/start` `/menu` `/build` `/request` `/plans` `/usage` `/admin` `/broadcast` `/grant` `/cancel`

## Deploy to Render

1. Push this repository to GitHub.
2. Render Dashboard → **New → Blueprint** → select the repository.
   `render.yaml` creates one background worker (`python bot.py`) that runs 24/7.
3. Set `BOT_TOKEN` in the worker environment.
4. For persistent data across redeploys, attach a Render Persistent Disk and
   point `DATABASE_PATH` at a file on it (e.g. `/data/venox.db`).

## GitHub integration

`.github/workflows/ci-deploy.yml` compiles both files, runs a database smoke test
on every push/PR, and triggers Render deploy hooks on `main`/`master`. Add repo
secrets `RENDER_BOT_DEPLOY_HOOK` (and optionally `RENDER_WEB_DEPLOY_HOOK`) to
enable automatic deploys.
