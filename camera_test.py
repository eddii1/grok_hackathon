import os
import sys
import time
import cv2
import threading
from pathlib import Path
from djitellopy import tello, Tello

# Reconfigure stdout for utf-8 if needed
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 1. Resolve Drone IP (from saved .drone-ip or fallback)
IP_FILE = Path(__file__).parent / "scripts" / ".drone-ip"
if IP_FILE.exists():
    DRONE_IP = IP_FILE.read_text().strip()
else:
    DRONE_IP = "10.37.75.76"

OUTPUT_FILENAME = "drone_flight_video.avi"
FPS = 20.0
FRAME_WIDTH = 960
FRAME_HEIGHT = 720

# Station-mode patch for djitellopy to send UDP commands without blocking on missing 'ok' text replies
def station_send_control(self, cmd, timeout=7):
    print(f">> Flight Command: {cmd}", flush=True)
    tello.client_socket.sendto(cmd.encode("utf-8"), self.address)
    return True

tello.Tello.send_control_command = station_send_control

# Flag to control the background video recording loop
keep_recording = True


def record_video(drone, output_path):
    global keep_recording

    frame_read = drone.get_frame_read()
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    out = cv2.VideoWriter(output_path, fourcc, FPS, (FRAME_WIDTH, FRAME_HEIGHT))

    print("[Video] Recording thread started...", flush=True)
    recorded_frames = 0

    while keep_recording:
        frame = frame_read.frame
        if frame is not None and frame.size > 0 and frame.mean() > 5:
            # Convert DJITelloPy RGB to OpenCV BGR
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            resized_frame = cv2.resize(frame_bgr, (FRAME_WIDTH, FRAME_HEIGHT))
            out.write(resized_frame)
            recorded_frames += 1
        time.sleep(1.0 / FPS)

    out.release()
    print(
        f"[Video] Recording completed: {recorded_frames} frames saved to '{output_path}'.",
        flush=True,
    )


def main():
    global keep_recording

    print(f"Connecting to Drone at {DRONE_IP}...", flush=True)
    drone = Tello(host=DRONE_IP)
    drone.connect(wait_for_state=True)

    # Check telemetry
    state = drone.get_current_state()
    bat = state.get("bat", drone.get_battery())
    print(f"Connected successfully! Battery: {bat}%, Height: {state.get('h', 0)}cm", flush=True)

    # 2. Initialize Camera Feed
    print("[Camera] Starting video stream...", flush=True)
    drone.streamon()
    time.sleep(2)  # Sensor warmup

    frame_read = drone.get_frame_read()
    # Wait for first valid frame before flight
    for _ in range(15):
        f = frame_read.frame
        if f is not None and f.mean() > 5:
            print("[Camera] Feed active and streaming.", flush=True)
            break
        time.sleep(0.3)

    # 3. Launch Recording Thread in Background
    recorder_thread = threading.Thread(target=record_video, args=(drone, OUTPUT_FILENAME))
    recorder_thread.daemon = True
    recorder_thread.start()

    try:
        # 4. Flight Sequence: Takeoff -> 360 rotation -> Land
        print("[Flight] Taking off...", flush=True)
        drone.takeoff()
        time.sleep(5)  # Stabilization at ~1m hover

        print("[Flight] Performing 360-degree rotation while recording...", flush=True)
        drone.rotate_clockwise(360)
        time.sleep(8)  # Full 360 rotation duration

        print("[Flight] Landing safely...", flush=True)
        drone.land()
        time.sleep(3)  # Touchdown

    except Exception as e:
        print(f"[Warning] Emergency / Error during flight: {e}", flush=True)
        try:
            drone.land()
        except Exception:
            pass

    finally:
        # 5. Stop Recording and Clean Up
        keep_recording = False
        recorder_thread.join(timeout=5)

        try:
            drone.get_frame_read().stop()
            drone.streamoff()
        except Exception:
            pass

        try:
            drone.end()
        except Exception:
            pass

        print(f"[Done] Flight complete! Video saved to '{OUTPUT_FILENAME}'.", flush=True)


if __name__ == "__main__":
    main()
