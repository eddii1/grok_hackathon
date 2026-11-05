# grok_hackathon

Team repo for the Grok Hackathon at the Museum, Pavia (2026-11-04/05).

Clone with the submodules:

```sh
git clone --recurse-submodules https://github.com/eddii1/grok_hackathon.git
```

- [`backend/`](https://github.com/eddii1/grok_hackathon_backend) - submodule: drone harness, perception, Grok agent, API. **Team task list: [`backend/TASKS.md`](https://github.com/eddii1/grok_hackathon_backend/blob/main/TASKS.md).**
- [`frontend/`](https://github.com/eddii1/grok_hackathon_frontend) - submodule: web UI (`app/`) and pitch deck (`slides/`).
- [`AGENTS.md`](AGENTS.md) - context for coding agents (Cursor, Claude Code, Grok Build): tracks, rules, hardware, security.
- [`docs/plan.md`](docs/plan.md) - what we are building: architecture, interface contracts, work split, timeline.
- [`docs/tracks.md`](docs/tracks.md) - the ten proposed tracks, full cards.
- [`docs/ideas-rating.md`](docs/ideas-rating.md) - our ideas rated against the tracks.
- [`docs/hardware/robomaster-tt/`](docs/hardware/robomaster-tt/) - DJI RoboMaster TT drone: SDK 3.0 reference, official PDF, Python SDK docs and examples.

## Run the SEEK dashboard with the recorded flight

Requires Git, Node.js 22+, and [uv](https://docs.astral.sh/uv/getting-started/installation/).
No drone or drone Wi-Fi is needed. Use your own xAI API key for real Grok decisions;
never put keys in the frontend or commit `.env`.

```sh
git clone --recurse-submodules https://github.com/eddii1/grok_hackathon.git
cd grok_hackathon/backend
uv sync
cp .env.example .env
```

Set `XAI_API_KEY` in `backend/.env`, keeping the other example settings. Then, in that terminal:

```sh
uv run fleet-viewer --video ../drone_flight_video.avi
```

The recording is included in the parent repo, not the backend repo. First launch downloads
the depth model and can take longer. Wait for the backend's localhost URL before opening the UI.

In a second terminal, from the cloned repo:

```sh
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173/** (or the address Vite prints). The backend runs at
http://localhost:8001; the frontend proxies `/api` there. This is the real dashboard and
Grok agent over recorded footage, not a real flight or a physically accurate simulator.
Start a search for something actually visible in the recording and follow the dashboard's
height-ready and approval prompts. `http://localhost:5173/?sim` is a separate browser-only
mock and does not use the recording or Grok.

### Prompt to send to a teammate's coding assistant

> Set up https://github.com/eddii1/grok_hackathon with recursive submodules. Read AGENTS.md
> and docs/plan.md. Run the existing SEEK single-player live dashboard using the included
> drone_flight_video.avi recording, not a webcam, real drone, multiplayer, or the ?sim page.
> Install backend dependencies with uv sync and frontend dependencies with npm ci.
> If backend/.env is absent, copy backend/.env.example; ask me to enter my own XAI_API_KEY
> locally without displaying or committing it. Preserve an existing .env. Start
> `uv run fleet-viewer --video ../drone_flight_video.avi` from backend and `npm run dev`
> from frontend. Wait for depth-model loading, verify both services, and give me the
> dashboard URL. Do not rewrite the app or change interfaces. Report any setup blocker.
