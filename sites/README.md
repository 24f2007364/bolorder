# BolOrder — ChatGPT Sites edition

This edition preserves the HTML/CSS/vanilla-JavaScript interface and Sarvam models from the Python MVP while running the backend in the Sites Cloudflare Worker runtime. The original FastAPI application remains at https://github.com/24f2007364/bolorder.

Production order state persists in the Sites-managed D1 database. Each browser receives a random HttpOnly session cookie and an independent demo workspace. The session lasts 30 days; clearing browser cookies starts a fresh workspace. Example customers, stock and prices are fictional. Each workspace supports up to 100 orders. This is a demonstration, not a multi-tenant production ERP.

A shared access password protects the deployed application. Username: `bolorder`. Runtime secrets `SARVAM_API_KEY` and `APP_ACCESS_PASSWORD` are configured in Sites and never committed. Obtain the generated access password from the owner. The owner can rotate it using the Site environment settings.

## Order correctness

Amounts use integer paise. Cart edits validate SKU IDs, carton quantities and delivery dates. Substitution is never automatic. Only a separately confirmed, currently reviewed cart can reserve stock. A single version-checked update stores the complete workspace, making stock, order number and confirmation one atomic change. On conflict, deterministic business logic retries against current state. AI interpretation is not repeated during the retry. Request IDs deduplicate turns, and completed confirmations return the original order.

Cloud speech uses the official Sarvam HTTP endpoints because the Worker cannot run the Python SDK: Saaras v4 with keyterms, Sarvam-105B function calls, and Bulbul v3 WAV speech. No other AI provider is used. Browser audio is converted to 16 kHz mono WAV before upload.

The exact Raja Stores demonstration ends at ₹24,624, with 10 atta, 3 Maggi, 2 Yippee and 4 Parle-G cartons. Demo Mode uses bundled prerecorded Sarvam audio and a scripted flow; live mode uses the supplied Sarvam key. Notifications are simulated. Invoice output is print-friendly HTML. The cloud edition does not expose the local Python telephony adapter; actual phone integration remains a separate setup task.

## Development

`npm install`, `npm run db:generate` (only when the schema changes), `npm test`, `npm run build`.

`npm run dev` runs a local preview at port 8001. Its local-only credentials are `bolorder` / `local-preview-access-only`. The preview uses Node's SQLite adapter against the same SQL migrations and Worker handlers. Set `SARVAM_API_KEY` in the shell only if testing live audio. Local preview state stays in ignored `.sites-runtime`.

Sites applies generated, schema-only Drizzle migrations before uploading the Worker. No production tables are created or altered during requests. Runtime reads use prepared D1 statements. Source packaging contains the bundled Worker, HTML/CSS/JS, prerecorded audio and migrations, with no Python environment or local database.

Request limits: 15 AI requests/minute per browser, 40/minute site-wide, and 1,000/day site-wide. These are demonstration limits, not Sarvam monetary caps. Provider outages return readable errors and leave the last saved cart intact. A browser that loses its session cookie cannot retrieve an earlier workspace without the original session. The app is intended for invited testers who know the shared access password.
