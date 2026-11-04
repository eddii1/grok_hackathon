# RoboMaster TT SDK 3.0 - command reference

A Markdown transcription of the official **RoboMaster TT SDK 3.0 User Guide** (V1.0, 2021.04, Ryze Tech), the PDF next to this file: [`Tello_SDK_3.0_User_Guide_en.pdf`](Tello_SDK_3.0_User_Guide_en.pdf). Source: https://dl.djicdn.com/downloads/RoboMaster+TT/Tello_SDK_3.0_User_Guide_en.pdf. When this file and the PDF disagree, the PDF wins.

## Connection

The drone is controlled with plain-text commands over Wi-Fi UDP.

| Channel | Direction | Address | Notes |
|---|---|---|---|
| Commands and responses | PC <-> drone | `192.168.10.1:8889` (UDP) | Send `command` first to enter SDK mode. |
| State | drone -> PC | listen on `0.0.0.0:8890` (UDP) | Starts after SDK mode is on. Format in [State string](#state-string). |
| Video | drone -> PC | listen on `0.0.0.0:11111` (UDP) | Send `streamon` first. |

- **Auto-land safety:** if the drone receives no command for 15 s after finishing the last one, it lands by itself. The `[TELLO] battery?` polling that the open-source controller sends does not count.
- **Wi-Fi reset:** with the drone on, hold the power button for 5 s. The drone reboots, and when the status light flashes yellow quickly the SSID and password are back to factory defaults (open network).
- Ports can be changed with `port info video`.

## Command types and responses

- **Control command** (`xxx`): returns `ok`, or `error` / a result code on failure.
- **Setting command** (`xx a`): sets a new value `a`. Returns `ok`, or `error` / a result code.
- **Read command** (`xx?`): returns the current value.

## Control commands

| Command | Description | Response |
|---|---|---|
| `command` | Enter SDK command mode. | `ok` / `error` / `unactive` |
| `takeoff` | Auto takeoff. | `ok` / `error` |
| `land` | Auto landing. | `ok` / `error` |
| `streamon` | Turn on the video stream. | `ok` / `error` |
| `streamoff` | Turn off the video stream. | `ok` / `error` |
| `emergency` | Stop the motors immediately (the drone drops). | `ok` / `error` |
| `up x` | Fly up x cm. x = 20-500 | `ok` / `error` + status |
| `down x` | Fly down x cm. x = 20-500 | `ok` / `error` + status |
| `left x` | Fly left x cm. x = 20-500 | `ok` / `error` + status |
| `right x` | Fly right x cm. x = 20-500 | `ok` / `error` + status |
| `forward x` | Fly forward x cm. x = 20-500 | `ok` / `error` + status |
| `back x` | Fly backward x cm. x = 20-500 | `ok` / `error` + status |
| `cw x` | Rotate clockwise x degrees. x = 1-360 | `ok` / `error` + status |
| `ccw x` | Rotate counterclockwise x degrees. x = 1-360 | `ok` / `error` + status |
| `motoron` | Enter Motor-On mode (Note 1). | `ok` / `error` |
| `motoroff` | Exit Motor-On mode. | `ok` / `error` |
| `throwfly` | Throw to launch: throw the drone horizontally within 5 s of sending the command. | `ok` / `error` |
| `flip x` | Flip in direction x: `l` left, `r` right, `f` forward, `b` back. | `ok` / `error` |
| `go x y z speed` | Fly to (x, y, z) at speed cm/s. x, y, z: -500 to 500; speed: 10-100. x, y and z cannot all be between -20 and 20 at the same time. | `ok` / `error` + status |
| `stop` | Stop moving and hover immediately. | `ok` / `error` |
| `curve x1 y1 z1 x2 y2 z2 speed` | Fly a curve through (x1, y1, z1) to (x2, y2, z2) at speed cm/s. Arc radius must be 0.5-10 m, otherwise a reminder is returned. Coordinates: -500 to 500; speed: 10-60. x, y and z cannot all be between -20 and 20 at the same time. | `ok` / `error` + status |
| `go x y z speed mid` | Fly to (x, y, z) in the coordinate system of mission pad `mid` (Note 2). x, y: -500 to 500; z: 0-500; speed: 10-100 cm/s. Same ±20 rule. | `ok` / `error` + status |
| `curve x1 y1 z1 x2 y2 z2 speed mid` | Curve in the coordinate system of mission pad `mid`. x, y: -500 to 500; z: 0-500; speed: 10-60. Radius 0.5-10 m. Same ±20 rule. | `ok` / `error` + status |
| `jump x y z speed yaw mid1 mid2` | Fly to (x, y, z) in the `mid1` pad's system and hover, then find pad `mid2`, move to (0, 0, z) above it and set the yaw (z > 0). | `ok` / `error` + status |
| `reboot` | Reboot the drone. | no response on success / `error` |

Coordinate frame (from the Python SDK docs): without a mission pad, +x is the drone's front and +y its left.

## Setting commands

| Command | Description | Response |
|---|---|---|
| `speed x` | Set the current speed to x cm/s. x = 10-100 | `ok` / `error` |
| `rc a b c d` | Virtual sticks: a roll, b pitch, c throttle, d yaw, each -100 to 100. | no response |
| `wifi ssid pass` | Change the drone's own Wi-Fi SSID and password. With the open-source controller attached the SSID gets the `RMTT-` prefix, otherwise `TELLO-`. | `OK, drone will reboot in 3s` |
| `mon` | Enable mission pad detection (downward by default). | `ok` / `error` |
| `moff` | Disable mission pad detection. | `ok` / `error` |
| `mdirection x` | 0 = downward, 1 = forward, 2 = both. Run `mon` first. One direction detects at 20 Hz; both alternate at 10 Hz each. | `ok` / `error` |
| `ap ssid pass` | Switch to station mode and join the router `ssid`. | `OK, drone will reboot in 3s` |
| `wifisetchannel xxx` | Set the Wi-Fi channel of the open-source controller (controller only). Clear the Wi-Fi info first, and pick a channel legal in your country. | `ok` / `error` |
| `port info video` | Set the state and video ports (1025-65535). | `ok` / `error` |
| `setfps fps` | Video frame rate: `high` 30 fps, `middle` 15 fps, `low` 5 fps. | `ok` / `error` |
| `setbitrate bitrate` | Video bit rate 0-5: 0 auto, 1-5 = 1-5 Mbps. | `ok` / `error` |
| `setresolution resolution` | Video resolution: `high` 720p, `low` 480p. | `ok` / `error` |

## Read commands

| Command | Description | Response |
|---|---|---|
| `speed?` | Current set speed (cm/s). | x (10-100) |
| `battery?` | Battery percentage. | x (10-100) |
| `time?` | Motor running time (s). | x |
| `wifi?` | Wi-Fi SNR. | SNR |
| `sdk?` | SDK version number. | xx (>= 20) |
| `sn?` | Serial number. | SN |
| `hardware?` | Whether the open-source controller is attached. | `TELLO` / `RMTT` |
| `wifiversion?` | Wi-Fi version of the open-source controller (controller only). | `wifivx.x.x.x` |
| `ap?` | Name and password of the router to connect to (controller only). | name and password |
| `ssid?` | Current SSID (controller only). | STA mode: factory SSID; AP mode: user SSID and password |
| `multiwifi ssid pass` | Set the SSID and password of the open-source controller, so it can act as a router that several devices connect to. | `ok` / `error` |

## Open-source controller (ESP32) commands

These drive the top LED, the 8x8 dot-matrix display and the ToF range sensor on the TT expansion kit. Factory firmware only (the User Manual explains how to restore it).

Send them over UDP like any other command, with the `EXT` prefix:

| Command | Description | Response |
|---|---|---|
| `EXT led r g b` | Top LED in a fixed colour. r, g, b: 0-255 | `led ok` / `error` |
| `EXT led br t r g b` | Top LED pulses at frequency t (0.1-2.5 Hz) up to colour (r, g, b). | `led ok` / `error` |
| `EXT led bl t r1 g1 b1 r2 g2 b2` | Top LED alternates between two colours at frequency t (0.1-10 Hz). | `led ok` / `error` |
| `EXT mled g xxxx` | Show a pattern on the dot matrix (Note 3). | `mled ok` / `error` |
| `EXT mled l/r/u/d r/b/p t xxxx` | Scroll a string (max 70 chars) left/right/up/down, in red/blue/purple, at t frames/s (0.1-2.5). | `mled ok` / `error` |
| `EXT mled l/r/u/d g t xxxx` | Scroll a pattern (Note 3) at t frames/s (0.1-2.5). | `mled ok` / `error` |
| `EXT mled s r/b/p xxxx` | Show one static ASCII character, or `heart`, in red/blue/purple. | `mled ok` / `error` |
| `EXT mled sg xxxx` | Set the boot animation pattern (Note 3). | `mled ok` / `error` |
| `EXT mled sc` | Clear the boot animation. | `mled ok` / `error` |
| `EXT mled sl n` | Dot-matrix brightness, n: 0-255. | `mled ok` / `error` |
| `EXT tof?` | Read the ToF distance sensor. | `tof xxxx` in mm; 8192 = out of range |
| `EXT version?` | ESP32 firmware version. | `esp32vx.x.x.x` |

When you program the ESP32 itself, it sends `[TELLO] <command>` over its serial port to the drone, and every reply comes back with the prefix `ETT ` and a `\r\n` suffix. Example: ESP32 sends `[TELLO] takeoff`, the drone replies `ETT ok\r\n`.

## Notes

1. **Motor-On mode** spins the propellers slowly while the drone is on the ground, ready for takeoff, which also cools the drone and avoids overheating shutdowns. Only available in static standby; the drone leaves the mode on takeoff.
2. **Mission pad IDs:** `m1`-`m8` are the pad numbers; `m-1` is the first pad Tello's algorithm recognises; `m-2` is the nearest pad.
3. **Dot-matrix patterns** are strings of up to 64 characters from `r` (red), `b` (blue), `p` (purple) and `0` (off), one per LED in order. Example: `rrrbb0ppp` lights LEDs 0-2 red, 3-4 blue, 5 off, 6-8 purple; the rest stay off.

## Mission pad restrictions

`mon`, `moff`, `mdirection x`, `go x y z speed mid`, `curve x1 y1 z1 x2 y2 z2 speed mid` and `jump x y z speed yaw mid1 mid2` need mission pads. The `go`, `curve` and `jump` pad variants only work with downward detection on.

## State string

The drone pushes one line per update to port 8890:

```
mid:%d;x:%d;y:%d;z:%d;mpry:%d,%d,%d;pitch:%d;roll:%d;yaw:%d;vgx:%d;vgy:%d;vgz:%d;templ:%d;temph:%d;tof:%d;h:%d;bat:%d;baro:%f;time:%d;agx:%f;agy:%f;agz:%f;\r\n
```

| Field | Meaning |
|---|---|
| `mid` | Detected mission pad ID. -2 = detection off; -1 = on but no pad seen. |
| `x`, `y`, `z` | Position relative to the detected pad (cm). -200 = detection off; -100 = no pad seen. |
| `mpry` | Pitch, roll, yaw relative to the pad (degrees); 0 if no pad. |
| `pitch`, `roll`, `yaw` | Attitude (degrees). |
| `vgx`, `vgy`, `vgz` | Speed on each axis (dm/s). |
| `templ`, `temph` | Lowest and highest main board temperature (°C). |
| `tof` | ToF distance (cm). |
| `h` | Height relative to the takeoff point (cm). |
| `bat` | Battery percentage. |
| `baro` | Barometer height (m). |
| `time` | Motor running time (s). |
| `agx`, `agy`, `agz` | Acceleration on each axis (cm/s²). |

The PDF's example line stops at `baro`, but its field list also documents `time`, `agx`, `agy` and `agz`. Parse the line as `key:value` pairs rather than by position.
