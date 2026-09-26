# Online deployment

Prepared for Render with native Python (no Docker required). No remote service or GitHub repository is created until an account is connected and the deployment is actually run.

## Free demonstration

1. Push this folder as the repository root. `.env`, SQLite databases, logs and caches are excluded. Never paste the Sarvam key into source or a commit.
2. In Render, create a Blueprint from the repository. `render.yaml` selects the free web service in Singapore, builds the pinned dependencies, runs one FastAPI worker and checks `/healthz`.
3. Set `SARVAM_API_KEY` using Render's secret environment setting. The Blueprint generates `APP_ACCESS_PASSWORD`. Its username is `bolorder`; share that password only with invited testers. The browser prompts for it on first access.
4. Wait for the deploy to become live. Verify `/healthz` returns `{"status":"ok"}`, unauthenticated `/api/bootstrap` returns 401, and the sample order completes after sign-in.
5. Open the generated HTTPS URL. HTTPS enables browser microphone permissions. Use Live Sarvam for speech or Demo Mode for the bundled rehearsal.

**Free storage is temporary:** Render's free filesystem is lost on restarts and redeploys. It is suitable for a hackathon demonstration with fictional seed data, not retained business orders. No paid plan has been authorized or provisioned. A durable installation needs a paid persistent disk mounted at `/var/data` and `DATABASE_PATH=/var/data/bolorder.sqlite3`. Keep one service instance and one worker while using SQLite and in-process request limits.

## Access and hosting configuration

- `PUBLIC_DEPLOYMENT=true` requires a password of at least 16 characters; otherwise startup fails closed.
- The shared login gates the HTML, files and browser APIs. `/healthz` is public; the phone adapter retains its separate bearer-token validation.
- Requests are limited per client: 15 AI-bound requests and 60 writes per minute, with a process-wide ceiling of 40 AI-bound requests per minute. These are basic demo limits, not billing caps. Set provider spending limits separately if needed.
- Render supplies `RENDER_EXTERNAL_URL`, used for exact browser-origin checks. Other hosts must set `PUBLIC_ORIGIN` to the deployed HTTPS origin.
- Invited testers share one distributor workspace and see its orders. This is not an isolated multi-tenant product.
- `DEMO_MODE=true` forces newly started orders into the scripted demonstration. For a strictly offline public demo, do not supply a Sarvam API key.

## Container alternative

The Dockerfile packages only application code and dependencies, runs as an unprivileged user, and uses `/data/bolorder.sqlite3`. Supply `APP_ACCESS_PASSWORD`, `SARVAM_API_KEY` and `PUBLIC_ORIGIN` as host-managed secrets. Mount persistent storage at `/data` if orders must survive replacement. A Docker build has not been performed on this computer because Docker is not installed.

## Verification

From the repository root, run `python -m pytest -q`. The tests cover hosted authentication, rejected cross-origin writes, request limits, health checks and the existing order-safety checks.

References: [Render FastAPI deployment](https://render.com/docs/deploy-fastapi), [Blueprint specification](https://render.com/docs/blueprint-spec), [free service limitations](https://render.com/docs/free), [persistent disks](https://render.com/docs/disks).
