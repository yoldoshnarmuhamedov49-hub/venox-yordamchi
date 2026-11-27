# Venox Yordamchi — SaaS Bot Constructor

Telegram bot + Web Mini App dashboard: 144 ready-made bot templates, a custom
bot builder, subscription tiers, card payments with manual receipt review, and
a custom bot development request form.

## Features

- **Identity:** Venox Yordamchi — Web Mini App platform, 144 bot templates in 12 categories (E-commerce, Ta'lim, Kontent, AI & Utility, ChatGPT & AI, SMM, Crypto, O'yin, Biznes, Sog'liq, Xizmatlar, Foydali vositalar), custom bot builder.
- **Dashboard (`index.html`):** searchable/filterable template catalog, Free/Standart/Ultra Pro pricing with detailed features, card + receipt instructions, custom bot request form, full Telegram light/dark theme integration.
- **Tiers:** Free (0 UZS), Standart (60,000 UZS / 30 days), Ultra Pro (150,000 UZS / 90 days).
- **Admin:** ID `8527026238` (@THE_VENOX) — permanent Ultra Pro/VIP with unlimited access, plus an admin panel for receipt review, broadcast, and manual VIP grants.
- **Payments:** Card `5614 6830 1549 1525`. User sends a receipt screenshot; it is forwarded to the admin with **Approve / Reject** buttons and the tier activates automatically on approval.
- **Deployment:** Render background worker (24/7 polling) + Web Mini App web service; GitHub Actions CI and Render deploy hooks.

## Local run

```bash
python -m pip install -r requirements.txt
cp .env.example .env        # add your BOT_TOKEN
python bot.py               # Telegram bot + Web Mini App in one process
python bot.py --webapp      # HTTP-only dashboard on http://localhost:8000
```

`python bot.py` starts the HTTP server in a background thread and then runs the
Telegram bot with long polling. The token is read from the environment or a
local `.env` file; it is never committed. The in-chat **🚀 Mini App ni ochish**
button opens the dashboard served from `index.html`.

## Bot commands

`/start` `/menu` `/build` `/plans` `/usage` `/admin` `/broadcast` `/grant` `/cancel`

## Deploy to Render

1. Push this repository to GitHub.
2. Render Dashboard → **New → Blueprint** → select the repository.
   `render.yaml` creates two services:
   - `venox-yordamchi-bot` — background worker running `python bot.py` (24/7).
   - `venox-yordamchi-miniapp` — web service running `python bot.py --webapp`, serving `index.html`.
3. In the worker service, set `BOT_TOKEN` and `MINI_APP_URL` to the miniapp
   service URL (Render → Web Service → URL, e.g.
   `https://venox-yordamchi-miniapp.onrender.com`). The bot then shows the
   **🚀 Mini App ni ochish** button in every chat.
4. For persistent data across redeploys, attach a Render Persistent Disk and
   point `DATABASE_PATH` at a file on it (e.g. `/data/venox.db`). Without a disk,
   SQLite lives inside the service filesystem and resets on each deploy.
   Published Mini App links carry their config in the URL, so they keep working
   even when the worker and web service have separate databases.

## GitHub integration

`.github/workflows/ci-deploy.yml` compiles both files, runs a database smoke test
on every push/PR, and triggers Render deploy hooks on `main`/`master`. Add repo
secrets `RENDER_BOT_DEPLOY_HOOK` and `RENDER_WEB_DEPLOY_HOOK` (Render → service →
Settings → Deploy Hook) to enable automatic deploys.
