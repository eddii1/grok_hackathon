# grok_hackathon

Team repo for the Grok Hackathon at the Museum (Ctrl+Alt Museum, Pavia), 4-5 November 2026. The minimum demo must run **Thursday 5 Nov by 16:00** on a new case the jury picks; pitches run 16:00-19:00.

## Status

Building our own idea (not one of the tracks): a fleet command platform where an operator tasks drones and other devices in plain language and Grok plans the mission ("find the person in the red jacket, follow them, take a photo"). First prize is a 30k startup grant, so the demo must read as an investable product. [`docs/plan.md`](docs/plan.md) holds the architecture, the interface contracts between workstreams, the work split and the timeline. Read it before changing any interface, and keep the contracts there in sync with the code. The team task list is [`backend/TASKS.md`](backend/TASKS.md).

`backend/` and `frontend/` are git submodules, each its own repo. Commit and push inside the submodule first, then commit the updated pointer in this repo; a parent commit made before the submodule push points at a commit nobody else can fetch.

## Tracks

All tracks are "proposed" and may change. Before scoping work or writing the README, read the chosen track's full card in [`docs/tracks.md`](docs/tracks.md): it has the inputs provided, the out-of-scope list and the exact measures.

| Track | Build | Hardware | Judged on |
|---|---|---|---|
| A CTRL+F: SEA (SEA Vision) | Find a requested object in a real scene ("Find this"), flag what was added, removed or moved ("What changed") | Arm 2, camera 2, dog slots | Objects found out of 10 new jury requests, time to find, false alarms |
| B Autonomous Company (Riso Scotti) | Zero-touch back office on synthetic EDI orders, delivery notes, invoices, disputes; humans review above a threshold | None | Reconciliation vs a deterministic baseline, disputes resolved with evidence, correct hand-offs, traceability |
| C Labelling from the Model Pack (Cristina Portinaro) | Read a model pack into a label spec; arm cycle accepts or rejects packs; new pack with no retraining | Arm 1, camera 1 | Spec correctness, rejects (accepting a wrong pack is worst), unattended cycle, jury's new pack |
| D Robot Dog Patrol (Riello) | Event -> mission -> check -> alert: scheduled patrol, phone-camera anomaly sends the dog, Grok describes, alert goes out, everything logged | Dog, phones as cameras | Event-to-arrival time, anomalies verified, false alarms forwarded, alert clarity, log completeness |
| 01 Research Radar | Map a research field from arXiv/OpenAlex/PubMed: named clusters, timeline, "What changed?" between two windows, sourced report | None | Retrieval quality, cluster coherence, dates, share of claims with a valid source, trends vs baseline |
| 02 GitHub Benchmark Arena | Find open-source tools, run them in containers on shared tasks with Grok as the fixed model, reproducible leaderboard | None | Reproducibility, adapter correctness, task quality, scoring transparency, install robustness, execution security |
| 03 Agent Failure Lab | Read agent traces, classify failures with per-step evidence, propose fixes, verify them by replay | None | Classification accuracy, finding the right step, verifiable explanations, effective fixes, regressions, added cost |
| 04 Voice Control | Italian voice commands -> 3-5 predefined arm skills, confirmation before every move, reliable "stop" | Arm 3 (no camera) | Commands correct out of 10, sentence-to-motion latency, ambiguous/out-of-reach handling, stop reliability |
| 05 Robot Skill Passport | Tutorials generated from arm manuals and videos, quizzes, a passport of acquired skills | 15 min on arm 3 | Time and errors with vs without the tutorial, no invented steps, checklist clarity |
| 06 LabOS | Chat custodian for a robotics lab: inventory, bookings, rules (no overlaps, 30-min slots, staff present), history | None | Requests handled on a test set incl. conflicts, rules never broken, time to book |

## Rules every deliverable meets

- Grok (API, Voice or Bot) is essential to how the system works.
- The demo generalises to a case the jury picks on the day.
- The repo ships a README, the data used, at least one result measured against a baseline, and known limitations. The organiser brief also asks for a 5-minute demo, quantitative results and a short roadmap.
- Data is public, synthetic or company-provided.
- Arms and the dog run in 30-minute staffed slots. Build against a mock or simulator first, and treat hardware time as the final check.
- Common rubric: still to be announced. Provisional, from the organiser repo: Innovation 25, Technical 25, AI usage 20, UX/UI 15, Business 15.

## Hardware

- **Drone: DJI RoboMaster TT.** Read [`docs/hardware/robomaster-tt/README.md`](docs/hardware/robomaster-tt/README.md) before writing drone code: it covers the library choice (DJI's `robomaster` package does not install on Apple Silicon), the no-internet Wi-Fi, the 15 s auto-land and retry hazards.
- No track card lists drones, so whether a drone project may enter a hardware track is still unconfirmed with the organisers.

## Grok

- Stack per the organiser brief: Grok API (function calling, structured outputs), built-in web and X search, code execution, Grok Voice (realtime), Imagine, Grok Bot. API credits are provided.
- Official Python SDK: `xai-sdk` (https://github.com/xai-org/xai-sdk-python). The key lives in `.env` as `XAI_API_KEY`, and `.env` stays out of git.

## Security

- The organiser repo https://github.com/aletheia/grok-bot-hackathon is read-only for us: read it through the GitHub web UI or API. Its upstream history contained planted malware, so it is never cloned, installed or run.
- Third-party code under evaluation (for example Track 02 candidates) runs only inside containers.
