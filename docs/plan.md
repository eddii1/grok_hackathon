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

### SEEK live demo update (2026-11-05)

The grid is now 25.5 x 25.5 m (51 x 51 cells, still 50 cm each). Column names extend past Z
using AA, AB, etc. Hop settings allow up to 10 cells / 5 m, the SDK's maximum forward command;
live depth/ToF clearance can still shorten each hop. This remains a bounded map, not unlimited navigation.

#### Multiplayer rover integration (MVP implementation; extended plan below)

**Updated multiplayer map/graph contract:** single-player code is unchanged. Drone and rover own
INDEPENDENT maps: the existing drone map remains flight-height geometry; `RoverMap` in
`fleet/multiplayer.py` accumulates ground support and rover-body obstacles only from the rover camera.
Both maps use the same starting origin (default zero offset, measured offsets remain configurable).
Rover breadcrumb routing uses ONLY its own grid plus fresh local depth/ToF checks. A cell red in the
drone display can be rover-free; unknown or blocked rover ground still causes a hold.
`/points` displays the drone's original geometry/grid with only actual rover pose/track overlaid, NOT
merged rover obstacle geometry. `/rover/points` exposes the separate rover scene. `/rover/graph` and
`/rover/state` expose real vision decisions and local checks/actions using the existing graph data shape.
Multiplayer renders the SAME `DecisionGraph` component for both devices; coordinator remains internal
and its explanatory UI panel is removed. These updated contracts supersede shared-geometry wording below.

**MVP implementation now present, not hardware-verified:** `backend/src/fleet/multiplayer.py` is a
separate service; `frontend/?multi` is the separate dashboard. Existing drone operation stays on `/`.
The coordinator assigns the shared goal through Grok, existing SEEK is the drone agent, and the rover
worker uses independent Grok vision plus bounded breadcrumb following. Shared rover depth points are
voxel-retained in the same map frame; rover navigation uses its own body/ground checks, not drone-free cells.

Run the existing rover dashboard on its SDK-capable host (restart it for the new read-only `/api/fleet`
and `/api/fleet/frame` endpoints with actual acquisition timestamps). Keep the regular drone backend
running as before. In a second backend terminal run:

```sh
uv run fleet-multiplayer --rover-url http://ROVER_HOST:5000 --drone-url http://127.0.0.1:8001
```

Restart Vite for the new proxy, then open `http://localhost:5173/?multi`. Measure rover start position
relative to the drone's takeoff origin, heading, fixed level camera height and full body dimensions
(including arm). Explicitly verify coordinate signs/clear starting ground in the calibration form.
Calibrate before EACH mission, enter the shared goal, Start team, adjust drone height, then Begin search.
Both devices/hosts must be reachable on the same LAN; no Wi-Fi pairing happens automatically.

**Intentional MVP limits:** rover drive is capped at 0.12 m/s with 5 Hz renewal and the bridge watchdog.
Unknown ground, stale video/odometry/depth, disabled collision braking or a blocked path causes a hold.
Autonomous rotation/detouring is NOT implemented: if a breadcrumb requires a heading change >12 degrees,
the rover holds and asks for manual alignment/recalibration rather than assuming unobserved side clearance.
Rover camera FOV defaults to 82.6 degrees in the form and must be measured/set before trusting geometry; depth
remains uncalibrated and no general under-table or collision-free guarantee is made. Shared map geometry
does not correct odometry drift. Candidate finds stop both devices for human review. Manual takeover in
this MVP stops BOTH workers; after rejected finds or manual alignment, recalibrate and restart deliberately.
This is not yet the full autonomous ground-path planner described below.

Rover code arrived in the PARENT repo at `rover/` (pulled through parent commit `e166cf3`),
not the backend submodule. Keep the existing single-player drone page and behavior unchanged.
Multiplayer is a separate entry/page and opt-in backend session, not a replacement for single player.

Verified bridge: `rover/app.py` serves Flask on port 5000: `GET /video_feed` (MJPEG),
`GET /api/status`, `GET /api/map/data`, `POST /api/control/drive` with `{vx, vy, vz}`
(body-relative m/s, m/s, degrees/s), and `POST /api/control/stop`. Reuse this HTTP bridge;
do not import its SDK into the drone environment or open a second rover control connection.
Its controller has a 0.8 s command watchdog and a forward-only proximity brake; drive responses
alone do not prove connection or successful movement. Check connection state and live odometry.

**Minimal multiplayer behavior:** one Grok coordinator owns the shared object description and
delegates to a drone agent and rover agent. Drone leads exploration. Rover follows completed,
timestamped drone ground-track breadcrumbs with a configurable trailing distance, while independently
looking for the SAME object in its own camera. Never follow an unexecuted proposed path or drive
straight toward the drone through obstacles. Route breadcrumbs through the rover's own clearance map;
if ground passage is blocked, stop and tell the coordinator rather than copying the drone's route.
Either agent can report a candidate; coordinator pauses the team and requests human confirmation.

The coordinator issues high-level goals (`explore`, `follow_and_search`, `hold`), not motor commands.
Two independent device workers execute concurrently. Rover steering/renewal runs locally around 5 Hz,
well inside its watchdog, independently of slow model calls. Clamp speed conservatively and stop on
stale odometry/video, disconnect, blocked clearance or manual takeover. No arm/gripper automation in MVP.

**Shared 3D map:** fuse both depth feeds only after measuring initial relative pose and camera mounts.
Convert rover coordinates/yaw explicitly: its controller uses x-forward and counter-clockwise yaw;
SEEK uses east/north and clockwise yaw from north. Share geometry and sightings but retain separate
drone-height and rover-body navigation layers. Under-table driving requires measured underside clearance,
body dimensions and ground support, not merely a free drone cell. Unknown clearance remains blocked.

**Multiplayer page:** two camera feeds, one shared 3D map with drone/rover markers and colored routes,
and a coordinator graph branching into parallel drone/rover lanes. Start/stop are explicit for the team;
manual input targets the selected device and suspends that device's autonomous worker. STOP ALL stops
the rover and hovers the drone; LAND and KILL remain drone-only. A stopped leader makes the follower hold.

**Implementation sequence:** (1) read-only bridge status/video, (2) calibrated rover pose and depth layer,
(3) bounded local rover steering with watchdog and stops, (4) breadcrumb following, (5) concurrent object
search and coordinator, (6) separate multiplayer page/graph. Preserve the current single-player path throughout.

- One coordinator assigns regions/goals to two concurrent device agents: drone and rover. Each device
  owns its command queue, local safety checks, memory, route and graph lane. The coordinator does not steer motors.
- Prefer complementary routes, not identical paths: drone covers open/high viewpoints; rover inspects
  low/occluded areas, including under tables only when its measured body clearance permits it.
- First integrate the rover adapter's camera, timestamped pose/odometry, dimensions, move/stop commands,
  status and emergency behavior. Keep drone-only mode working while the rover is absent.
- Both camera feeds use the depth model. Serialize inference through the existing model lock and drop
  stale frames independently per device so one feed cannot build a backlog or starve the other.
- Use one shared world frame, with a measured start offset/heading and camera mounting transform for
  each device. Do not fuse maps until alignment is established. Monocular depth and dead reckoning drift.
- Share geometry and sightings, NOT a single free/blocked grid: drone navigation uses flight-height
  clearance; rover navigation checks ground support, obstacles across its full body height/width, and
  table underside clearance. Drone-free does not mean rover-free, or vice versa.
- Reserve upcoming route segments in space AND height/time; avoid conflicting destinations. Stop both
  if shared localization becomes unreliable. Operator manual input overrides the selected device;
  clearly separate per-device stop from STOP ALL, drone LAND and drone-only KILL MOTORS.
- Dashboard: two labeled camera feeds, shared map with distinct device colors/routes, coordinator graph
  above parallel drone/rover lanes. Device selection controls manual input and approvals explicitly.
- Integration order: rover adapter alone, calibrated maps, dual feeds, independent agents, then coordinator
  allocation/reservations. No rover execution or interface assumptions are implemented before its push.

The live viewer uses polling (`/state`, `/points`, `/map.png`) and `/graph/stream` for the decision graph.
`/points.plan` is the current agent OR manual action, with `action`, `label`, `heading`, and `path` (grid
`[column, row]` pairs), plus `route` (the straight-leg endpoints actually flown). Plans remain visible throughout approval and execution, including Automatic mode,
and clear on completion, rejection or stop. `POST /goto/{cell}` publishes the operator's exact destination
through the same map contract. Autonomous search gotos choose distant unvisited corners of the reachable
known-free area for long scanning passes; manual destinations bypass this search policy, not obstacle checks.
Camera geometry already projects surfaces ahead using metric depth; the ~1 m look-ahead is a search/view
reference (`/points.state.camera_view`), not a physical camera offset or an extra metre added to obstacles.
Mapping pauses during translation because position is dead-reckoned after SDK completion; landed Tello
frames are not fused into the flight-height map. Before each hop, settled depth updates the map and checks
a 60 x 60 cm flight corridor. Hop size is a maximum: shorten to measured clearance minus the unchanged
60 cm stand-off, never below the SDK's 20 cm minimum. Recent measured blockers persist for 30 s at their
measured location. Up to two local reroutes retain the same destination; failed destinations cool down for
45 s, and Grok can choose a different reachable corner instead of being forced back onto a failed target.
`POST /cmd/stop` cancels agent/manual routes and sends immediate STOP/HOVER, bypassing the command queue.
It keeps motors and the airborne keepalive on, latches further motion off until a new operator action, and
never interrupts an already-started landing. LAND and KILL MOTORS remain separate controls.
Missions publish graph step `-1` immediately for takeoff/height setup, then pause before recon or any
model call, including in Automatic mode. `/state.height_waiting` enables Up/Down without cancelling the
mission; `/state.busy` disables confirmation while a command runs. `POST /agent/ready` confirms the chosen
height and rebuilds the map before recon. `/settings.takeoff_height_m` selects the next takeoff's target
within the existing 0.4-4 m limits; changing the setting does not itself move an airborne drone.
The graph UI bootstraps from `/graph`, streams updates, and polls `/graph` if the stream stalls. It shows
setup/recon/reasoning even before a mission rather than starting with an empty canvas.
Keyboard taps use `POST /manual/{command}?arg=...`: WASD/arrows move 20 cm, Q/E turn 15 degrees,
R/F adjust height 20 cm, Space/Escape hover, L lands. Inputs/contenteditable fields do not trigger shortcuts.
Each tap brakes immediately and invalidates old queued motion; only the newest pending manual command runs.
Manual input cancels autonomous reasoning/routes, except height tweaks during the mandatory setup pause
which preserve the pending goal. Limits, collision guards, and an in-progress landing still take precedence.

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

The claimable, task-level list is [`backend/TASKS.md`](https://github.com/eddii1/grok_hackathon_backend/blob/main/TASKS.md). Five workstreams. Each one has a stub-first start, so everyone is productive from the first hour.

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
