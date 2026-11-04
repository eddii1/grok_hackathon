# DJI RoboMaster TT (Tello Talent)

The team's drone: a Tello with the TT expansion kit (ESP32 open-source controller, top RGB LED, 8x8 dot-matrix display, forward ToF range sensor). Box photo: [`box.jpg`](box.jpg).

## What is here

| File | Use it for |
|---|---|
| [`sdk-3.0-reference.md`](sdk-3.0-reference.md) | Every UDP command, its parameter ranges and responses, the state string, and the `EXT` commands for the LED, matrix and ToF. Start here. |
| [`Tello_SDK_3.0_User_Guide_en.pdf`](Tello_SDK_3.0_User_Guide_en.pdf) | The official guide (V1.0, 2021.04), the source of the reference above. |
| [`python-sdk/`](python-sdk/) | DJI's `robomaster` Python SDK docs for drones (English, converted from https://robomaster-dev.readthedocs.io/en/latest/), plus the official drone and multi-drone examples. Apache-2.0, see [`python-sdk/LICENSE`](python-sdk/LICENSE). |
| [`python-sdk/api-reference.md`](python-sdk/api-reference.md) | `Drone`, `Flight`, `TelloCamera`, `TelloBattery` and `Action` APIs (docstrings in Chinese). |
| [`python-sdk/beginner_drone.md`](python-sdk/beginner_drone.md) | Tutorial: connect, query, LED, flight, video. |
| [`python-sdk/beginner_multi_robot.md`](python-sdk/beginner_multi_robot.md), [`multi_robot_drone_example.md`](python-sdk/multi_robot_drone_example.md), [`multi_robot_apis.md`](python-sdk/multi_robot_apis.md) | Flying several drones from one program (swarm). |
| [`python-sdk/connection.md`](python-sdk/connection.md), [`installs.md`](python-sdk/installs.md) | Connection modes and install steps. |
| [`python-sdk/examples/`](python-sdk/examples/) | `12_drone/`: one script per feature (takeoff, go, curve, mission pads, video, LED, matrix, ToF, station mode). `15_multi_robot/multi_drone/`: swarm scripts. |

## Which library to use

The drone speaks plain text over UDP, so any language works. There are three ways to drive it from Python:

1. **Raw UDP** (stdlib `socket`): send commands to `192.168.10.1:8889`, read state on `8890`, video on `11111`. About 30 lines, no dependencies, and full control over retries and timing.
2. **`djitellopy`** (MIT, `pip install djitellopy`, v2.5.0, Python >= 3.6): the most used community library. It decodes video with PyAV (`get_frame_read()`), parses state, and has `TelloSwarm` for several drones. Use `send_control_command("EXT led 255 0 0")` and `send_read_command("EXT tof?")` for the expansion kit.
3. **DJI `robomaster`** (official, Apache-2.0): the API documented in `python-sdk/`. **PyPI only ships wheels for CPython 3.6-3.8**: Linux x86_64/aarch64, Windows x64, and macOS **x86_64 only** (latest Mac build 0.1.1.61). No sdist exists, so it does not install on Apple Silicon with a current Python. Run it in an x86_64 Python 3.8 under Rosetta or Docker, or use option 1 or 2.

## Gotchas

- **The drone's Wi-Fi has no internet.** A laptop that joins `TELLO-`/`RMTT-xxxx` loses the Grok API. Either put the drone in station mode (`ap <ssid> <pass>`) on a router or phone hotspot you control, which also allows several drones, or give the laptop a second connection (USB or Ethernet tethering).
- **Send `command` first.** Nothing else is accepted until the drone is in SDK mode.
- **15-second auto-land.** If the drone gets no command for 15 s after finishing the last one, it lands. While hovering, keep sending something (`djitellopy` has `send_keepalive()`).
- **Retries can repeat a move.** `djitellopy` resends a command up to 3 times when no `ok` arrives. If the `ok` was lost over UDP, a move like `forward 100` runs twice. For flight commands, create `Tello(retry_count=1)` and decide on retries yourself.
- **Moves have minimums.** `up/down/left/right/forward/back` need 20-500 cm; `go` and `curve` reject targets where x, y and z are all within ±20 cm.
- **Several drones need a shared router.** In its default mode each drone is its own Wi-Fi network, so one PC reaches one drone at a time. To fly several from one PC, switch each drone to station mode with `ap <ssid> <pass>` (it reboots), then address them by IP. The `multi_drone` examples and `beginner_multi_robot.md` show the flow.
- **The open-source controller changes the SSID prefix** to `RMTT-` (plain Tello: `TELLO-`). `hardware?` returns `RMTT` when the kit is attached.
- **Emergency stop:** `emergency` cuts the motors at once, so the drone falls. `stop` makes it hover in place. Bind both to keys before the first flight.
- **Indoor flight (practical, not from the PDF):** the downward vision positioning needs light and a textured floor. Over a plain or shiny floor the drone drifts. Mission pads (`mon`, `go x y z speed m1`) give repeatable positions for demos.
