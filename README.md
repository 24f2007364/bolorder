# BolOrder

A local distributor workspace that turns a retailer's Hindi, Hinglish, Tamil, Bengali or English voice order into a checked cart, approved substitutions, a reserved sales order and a printable confirmation.

For online hosting, see [DEPLOYMENT.md](DEPLOYMENT.md). The repository includes a free Render Blueprint and a Dockerfile. Hosted mode adds a shared access password and basic request limits; the local workflow is unchanged.

## Run

Python 3.11+ is required. On this computer, dependencies and the private `.env` are already configured. From this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Open http://127.0.0.1:8000. The server binds to localhost. If it is already running, simply open the URL.

For a fresh installation:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and add your own key.
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On macOS/Linux use `python3`, `.venv/bin/python` and `cp .env.example .env` instead.

## Environment

| Variable | Default / purpose |
|---|---|
| `SARVAM_API_KEY` | Required for live speech and interpretation; server-side only |
| `DEMO_MODE` | `false`; `true` forces newly created orders into the scripted demo |
| `SARVAM_STT_MODEL` | `saaras:v4` |
| `SARVAM_CHAT_MODEL` | `sarvam-105b` |
| `SARVAM_TTS_MODEL` | `bulbul:v3` |
| `SARVAM_TTS_SPEAKER` | `shubh` |
| `VOICE_TOOL_TOKEN` | Optional bearer secret for the phone HTTP adapter |
| `DATABASE_PATH` | `app/data/bolorder.sqlite3`; seeded automatically |

Never commit `.env`. No API key is exposed in browser scripts. Restart the server after environment changes.

## The demo

Select Raja Stores and Live Sarvam. Tap the microphone, speak, and tap again to send. The browser must allow microphone access. Each turn is capped at 25 seconds. Chrome or Edge on localhost is recommended. Text input follows the same order path if recording is unavailable.

1. Say: “Kal ke liye 10 carton Aashirvaad atta, 5 carton Maggi aur 4 carton Parle-G bhej dena.”
2. The backend finds 10 cartons of atta, only 3 Maggi, and 20 Parle-G. It proposes 2 Yippee cartons without changing the order automatically.
3. Say: “Haan, 3 Maggi aur 2 Yippee kar do.”
4. Review 10 atta, 3 Maggi, 2 Yippee and 4 Parle-G. Total: **₹24,624.00**. Delivery defaults to tomorrow.
5. Say: “Haan confirm.” The final action also has a visible Confirm order button.
6. See the generated SO number, inventory reservation, printable confirmation and **simulated** customer message. Open Orders to find the completed order.

If a different confirmation phrase is unclear, the app asks for the explicit phrase or button. It never confirms merely because a substitute was accepted.

**Offline rehearsal:** choose Try sample order. This explicitly switches to Demo Mode. Click the three sample steps in sequence. Prerecorded Sarvam voice responses are bundled. No API call is required for the scripted flow. Demo stock is separate from live sample stock. Reset demo restores only demo stock and cancels open demo drafts; completed demo records remain in Orders.

Live sample stock is persistent: after completing the exact order, atta stock is exhausted. Use the separate demo pool for repeated rehearsals, or set `DATABASE_PATH` to a new filename and restart to get a fresh seeded live dataset. Do not delete an existing database containing orders you need.

## Architecture

```text
Browser microphone -> FastAPI -> Sarvam Saaras v4
Typed text -------------------> Sarvam-105B tool calls
                                  |
                 validated order + inventory services
                                  |
                 SQLite prices / stock / audit / orders
                                  |
                  explicit confirmation + transaction
                                  |
             reserve stock -> proforma HTML -> notification simulator
                                  |
                 Sarvam Bulbul v3 -> browser audio

Sarvam Voice Agents HTTP tool -> same FastAPI turn service (optional)
```

Vanilla HTML/CSS/JavaScript, FastAPI, Pydantic, SQLite and the official `sarvamai` Python SDK. No frontend framework, ORM, ERP, tax engine or secondary AI provider.

Sarvam handles Indic and code-mixed speech plus product/intent interpretation. The model sees catalog aliases and can call `search_products`, `get_product`, `check_inventory`, `find_alternatives`, `update_order_items`, `calculate_order_total`, `confirm_order`, `cancel_order` and `ask_clarification`. The batch update calls the deterministic inventory checks automatically. Customer identity is selected before the turn; phone identity uses the caller number. Internal functions also expose draft creation, single-item updates, reservation, document generation and notification simulation.

Prices use integer paise. Product IDs, quantities and dates are validated. Substitutes rank by category, normalized pack difference and price difference. The backend checks the cart revision before confirmation and uses `BEGIN IMMEDIATE` for confirmation, number allocation and stock reservation. Competing orders cannot take the same carton. Confirmation retries return the same order number. Turns are deduplicated by request ID. Drafts survive refresh through SQLite and the active order ID in local storage.

States are DRAFT, WAITING_FOR_CLARIFICATION, READY_FOR_CONFIRMATION, CONFIRMED, INVENTORY_RESERVED, COMPLETED and CANCELLED. Intermediate confirmation states are recorded in the audit log inside the transaction, while the final database state becomes COMPLETED only on successful commit.

## API choices verified 26 September 2026

| Capability | Choice | Reason |
|---|---|---|
| STT | `saaras:v4`, `POST /speech-to-text` | GA; code-mixed recognition and catalog keyterms |
| Reasoning / tools | `sarvam-105b`, `POST /v1/chat/completions` | Official function tools, validated arguments, Indic language coverage |
| Conversation variant | `sarvam-105b-conversations` is documented; configurable using `SARVAM_CHAT_MODEL` | Default stays with the reasoning model for order operations; no extra round trip for numerical readback |
| TTS | `bulbul:v3`, `POST /text-to-speech` | Stable voice output with `shubh`; WAV at 24 kHz |
| Voice Agents | Authenticated HTTP turn adapter | Browser is fully functional without a provisioned phone number |

Model API base is `https://api.sarvam.ai`, using `api-subscription-key`; the SDK handles authentication. Voice Agents uses a separate `X-API-Key`, organization and workspace scope. No beta model is needed. The live backend never silently switches to another provider or a demo response. Provider failures keep the existing cart and display a retry/demo option.

Official references: [changelog](https://docs.sarvam.ai/changelog), [STT](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe), [keyterms](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/how-to/keyterms), [chat tools](https://docs.sarvam.ai/api/api-guides-tutorials/chat-completion/overview), [models](https://docs.sarvam.ai/api/getting-started/models/sarvam-105b), [TTS](https://docs.sarvam.ai/api-reference/text-to-speech/convert), [SDK](https://docs.sarvam.ai/api/getting-started/sdks), [Voice Agents HTTP tools](https://docs.sarvam.ai/conversations/build/tools/https-tool).

Inter is loaded through the official Google Fonts service, with system fallbacks. An official reusable Google Sans web source was not established during verification. Icons use Google Material Symbols Rounded. No unofficial font mirrors, emojis or image dependencies are used.

## Tests and limits

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

If using the already installed shared environment on this computer, replace `.\.venv\Scripts\python.exe` with `..\..\.venv\Scripts\python.exe`.

Tests cover the complete scripted flow, no reservation before consent, explicit confirmation, stale revisions, retry idempotency, competing stock reservations with rollback, unknown products/customers, ambiguous descriptions, phone adapter authentication and isolated demo stock.

This is a single-process MVP with an optional shared-password gate for invited online testers. There are no individual user accounts, ERP writes, real messaging, tax calculations or live telephony deployment. Phone setup instructions are in `VOICE_AGENT_SETUP.md`. A production service needs individual access controls and further operational hardening. SQLite is sufficient for this demonstration, not a distributed order service. Confirmed orders are immutable in the MVP.

Speech is recorded per turn, not streamed. Microphone hardware and browser permissions must be checked on the presentation machine. Autoplay restrictions can require pressing Replay. Demo mode supports the documented Raja Stores script, not arbitrary speech; its bundled readback assumes the standard script. Live speech and language interpretation require Sarvam availability and credits. Print / Save as PDF uses the browser. Customer data, phone numbers and prices are fictional seed examples. Logs contain order text and actions but never API keys.
