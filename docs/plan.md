# Plan: Grok fleet command platform

Status: chosen 2026-11-04. Supersedes [`ideas-rating.md`](ideas-rating.md).

## The pitch in one line

**One operator commands a fleet of drones, rovers and cameras in plain language; Grok plans the mission, picks the right device and the right target, and the platform flies it.**

Example task: *"Find the person in the red jacket, follow them and take a photo."*

## What wins the grant

The first prize is a 30k grant to fund a startup, and the jury is half technical, half business. So the demo has to look like a **product** and the pitch has to look like a **company**:

- **Product:** a platform that is clearly device-agnostic (at least 2 devices on screen, even if one is simulated), a chat that turns intent into missions, and a human confirmation before anything acts on a person.
- **Company:** a paying customer segment, a market that already exists (drone-as-first-responder for police, search and rescue, security patrols, inspection), and comparables that show investors fund this: Auterion (drone OS), Anduril Lattice (multi-device command and control, defence), Skydio, Brinc and Flock Safety (drones as first responders). Verify every number before it goes on a slide.
- **Regulation as an asset:** in the EU, real-time remote biometric identification in public spaces by police is restricted by the AI Act. We identify **by description, not by face**, and a human confirms every target. Lead the business story with search and rescue, missing persons and event security, where the same feature is uncontroversial, then name police as the expansion market.

## Demo (5 minutes, the jury may change the target description)

1. The platform shows two devices: `drone-1` (the real RoboMaster TT) and `drone-2` (a second TT if we get one, otherwise the simulator).
2. The operator types: *"Find the person in the red jacket and take a photo."*
3. Grok answers with a plan, assigns `drone-1`, and asks for confirmation. The drone takes off and scans the room. The UI shows live video with numbered boxes around people.
4. Grok picks the box that matches ("box 3: red jacket, by the door") and shows its reason. The operator clicks **Confirm**.
5. The drone follows the target (a teammate walking slowly), takes the photo when the person is centred and close enough, and Grok checks the photo against the description.
6. The chat shows the photo and a short report. The drone lands.
7. One slide of numbers (see [Evaluation](#evaluation)), then the business slides.

Targets are always teammates who agreed to it, and no other attendee is filmed for the test set.

Because the jury picks the case, nothing is scripted to "red jacket": target selection takes any description ("the man with glasses", "the person holding a laptop").

## Architecture

```
Web UI (chat | video tile per device | device status | event log | STOP)
   |  WebSocket /ws (events both ways)   +   MJPEG /video/{device_id}
Backend (Python, FastAPI)
   |-- Agent: Grok with function calling, decides WHAT and WHO (slow, 1-3 s per call)
   |-- Skills: search, follow, take_photo, go_to, land (fast loops, 10-20 Hz)
   |-- Perception: person detector + tracker on each device's frames
   |-- Device registry -> DeviceAdapter
   |        |-- TelloAdapter (djitellopy, one per drone, own video port)
   |        |-- SimAdapter (plays recorded video, fakes state and moves)
   |-- Event log (every message, tool call, command, snapshot), used by the UI, the report and the evaluation
```

**The key design rule: Grok decides who, the local loop decides how.** Grok is too slow to steer a drone, so it is never in the control loop. Grok picks the target once from a frame with numbered boxes, and re-checks it when the tracker loses the target. The tracker and a simple proportional controller keep the target centred with `rc` commands at 10-20 Hz.

## Interfaces (agree on these first, then everyone works in parallel)

These four contracts are the only places where workstreams touch. Each one starts life as a stub that returns fake data, so nobody waits on anybody.

### 1. DeviceAdapter (owner: drone harness)

```python
class DeviceState(TypedDict):
    id: str
    kind: Literal["drone", "rover", "camera"]
    connected: bool
    flying: bool
    battery_pct: int
    height_cm: int
    yaw_deg: int

class DeviceAdapter(Protocol):
    id: str
    kind: str
    def state(self) -> DeviceState: ...
    def latest_frame(self) -> tuple[np.ndarray, float] | None: ...   # BGR frame, timestamp
    async def takeoff(self) -> None: ...
    async def land(self) -> None: ...
    async def hover(self) -> None: ...                                 # SDK "stop"
    async def move(self, forward_cm: int, left_cm: int, up_cm: int) -> None: ...
    async def rotate(self, cw_deg: int) -> None: ...
    def rc(self, left_right: int, fwd_back: int, up_down: int, yaw: int) -> None: ...  # -100..100, non-blocking
    async def emergency(self) -> None: ...
```

The adapter enforces the safety limits, so no caller can break them: max height 200 cm, `rc` values capped at ±40, keepalive under the 15 s auto-land, low-battery refusal below 25 %, and `hover()` whenever a command times out (never a blind retry).

### 2. Perception (owner: perception and control)

```python
class Detection(TypedDict):
    track_id: int
    box: tuple[int, int, int, int]   # x1, y1, x2, y2 in pixels
    confidence: float

def detect(frame) -> list[Detection]: ...                      # people only, with stable track IDs
def annotate(frame, detections) -> bytes: ...                  # JPEG with numbered boxes, for Grok and the UI
def follow_command(target: Detection, frame_shape) -> tuple[int, int, int, int]: ...  # rc values
def photo_ready(target: Detection, frame_shape) -> bool: ...   # centred and big enough
```

### 3. Agent tools (owner: agent)

Grok sees these functions; each returns JSON.

| Tool | Does |
|---|---|
| `list_devices()` | Devices with kind, state and capabilities. |
| `takeoff(device_id)` / `land(device_id)` | After operator confirmation for takeoff. |
| `search(device_id, description)` | Scans (rotate in steps, or a short sweep), collects candidates, then Grok picks a box from the annotated frames. Returns the chosen `track_id` and the reason, or "not found". |
| `confirm_target(device_id, track_id, reason)` | Shows the crop to the operator and waits for Confirm or Reject. |
| `follow(device_id, track_id, max_seconds)` | Runs the follow loop until a photo is ready, the track is lost, or time runs out. |
| `take_photo(device_id)` | Saves the current frame and returns `photo_id`. |
| `verify_photo(photo_id, description)` | Grok checks the photo against the description and returns match, confidence and reason. |
| `report(text, photo_ids)` | Final message in the chat. |

`stop_all` is **not** an agent tool. It is a UI button that goes straight to the device registry and always works, even if the agent is stuck.

### 4. UI events over `/ws` (owner: platform)

```jsonc
// backend -> UI
{"type": "chat", "role": "assistant", "text": "..."}
{"type": "device_state", "device": { /* DeviceState */ }}
{"type": "tool_call", "name": "search", "args": {...}, "result": {...}}
{"type": "confirm_request", "request_id": "r1", "device_id": "drone-1", "image_url": "/snapshots/...", "reason": "..."}
{"type": "photo", "photo_id": "p1", "url": "/photos/p1.jpg", "caption": "..."}
// UI -> backend
{"type": "user_message", "text": "..."}
{"type": "confirm_response", "request_id": "r1", "approved": true}
{"type": "stop_all"}
```

Video does not go over the WebSocket: each device has an MJPEG endpoint `/video/{device_id}` (with boxes drawn on it), which the UI shows with a plain `<img>`.

## Stack (chosen for speed)

- **Backend:** Python 3.11+, FastAPI, uvicorn. The drone and vision libraries are Python, so one process holds everything.
- **Drone:** `djitellopy` (MIT). DJI's `robomaster` package does not install on Apple Silicon (see [`hardware/robomaster-tt/README.md`](hardware/robomaster-tt/README.md)).
- **Detection and tracking:** Ultralytics YOLO (nano model, `classes=[0]` for people) with its built-in ByteTrack (`model.track(..., persist=True)`). It is AGPL-3.0: fine for the hackathon, and the roadmap swaps it for an Apache-licensed detector before the company ships.
- **Grok:** `xai-sdk`, with function calling for the agent and image input for target selection and photo checks. `XAI_API_KEY` in `.env`.
- **UI:** a local web app (React with Vite, or whatever the UI owner is fastest in). A website on localhost beats a desktop app here: same demo, no packaging work.

## Work split

Five workstreams. Each one has a stub-first start, so everyone is productive from the first hour.

| # | Workstream | Delivers | First hour |
|---|---|---|---|
| 1 | **Drone harness** | `TelloAdapter`, `SimAdapter`, device registry, safety limits, multi-drone networking (station mode, one video port per drone) | Connect to the TT, get video frames on a laptop, fly up 50 cm and land from code. **Answer the network question** (below). |
| 2 | **Perception and control** | `detect`, `annotate`, `follow_command`, `photo_ready`; the follow loop tuned on the real drone | Record 2-3 minutes of drone video of teammates walking (different clothes), run YOLO + tracking on it. |
| 3 | **Agent (Grok)** | Tool definitions, system prompt, agent loop, target selection prompt (numbered boxes -> `track_id` + reason), photo check, multi-device assignment | One Grok call with an annotated image that returns a box number as structured output. Measure the latency. |
| 4 | **Platform (backend API + UI)** | FastAPI app, `/ws`, MJPEG endpoints, UI with chat, video tiles, device cards, event log, confirm dialog, STOP | Skeleton app that talks to a fake device and a fake agent through the event contract. |
| 5 | **Evaluation, pitch and submission** | Test set, baseline, metrics, README numbers; deck, business model, comparables, demo script, backup video, portal submission | Write the demo script and the deck outline; book hardware and batteries with the organisers. |

**For 4 people:** merge 4 into 3 (agent person also owns the backend), and split 5 between everyone at the end. **For 6 people:** pair 1 and 2 on the real drone, and give 5 two people (one on evaluation, one on pitch).

Integration owner: whoever owns workstream 4 merges and keeps `main` runnable at all times.

## Timeline (demo Thursday by 16:00)

| By | Milestone |
|---|---|
| Wed 13:00 | Interfaces merged as stubs. Network question answered. Each workstream's first-hour task done. |
| Wed 18:00 | **Tracer bullet**: type "take off and tell me what you see" in the UI -> the drone takes off, video shows in the UI, Grok describes the scene, the drone lands. |
| Wed 23:00 | Find and select: Grok picks the right person from numbered boxes on recorded video and on the live drone. Follow loop works on the simulator. |
| Thu 09:00 | Full mission on the real drone: search -> confirm -> follow -> photo -> verify -> report. Second device on screen. |
| Thu 12:00 | **Feature freeze.** Evaluation runs, numbers into the README. Backup demo video recorded. |
| Thu 14:00 | Deck final. Three full rehearsals with the real drone, including a target description we did not prepare. |
| Thu 16:00 | Demo. |

## Evaluation

Every track requires "at least one result measured against a baseline".

- **Target selection accuracy:** about 30 staged frames (teammates in different clothes, 2-5 people per frame, with distractors such as two red tops) and a description for each. Grok's pick vs. a baseline that picks the box with the most pixels of the named colour. Report accuracy for both.
- **End-to-end mission:** 10 runs of "find X and take a photo" on the real drone. Report success rate (photo of the right person), time to photo, wrong-person photos, and how often the operator rejected a target.
- **Latency:** Grok selection time and follow-loop rate.

## Risks to clear early

1. **Network (blocks everything, answer by 13:00).** The drone's own Wi-Fi has no internet, so a laptop on it cannot reach Grok. Try: the TT in station mode (`ap <ssid> <pass>`) on a phone hotspot, with the laptop on the same hotspot, then check that video still arrives. If video fails in station mode: one drone in its own Wi-Fi (AP) mode, with internet for the laptop through a USB-tethered phone, and the simulator as the second device.
2. **Second drone.** Ask the organisers now whether we can have two TTs. The demo works with one real drone plus the simulator, but two real ones are a much stronger "fleet" moment.
3. **Flying indoors near people.** Slow `rc` limits, propeller guards on, only teammates as targets, keep 2 m of distance (by box size), STOP button and a keyboard shortcut for `emergency`.
4. **Wi-Fi congestion at the venue.** About 10 drones on 2.4 GHz in one room. Test in the venue early, and record the backup video on Thursday morning.
5. **Batteries.** A TT flies about 10 minutes. Ask how many batteries and chargers we get, and keep a charging rotation.
6. **Drift.** The TT positions itself from the floor texture. Fly over a textured floor or lay mission pads.
