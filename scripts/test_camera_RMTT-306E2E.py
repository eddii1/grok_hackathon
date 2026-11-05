"""RoboMaster TT / Tello Live Camera Stream & Broadcaster.

Connects to the drone, enables camera streaming (streamon), and opens
a high-framerate OpenCV desktop window with telemetry overlay.

Usage:
  python scripts/test_camera_RMTT-306E2E.py
  python scripts/test_camera_RMTT-306E2E.py --ip 192.168.10.1
"""

import argparse
import sys
import time

try:
    import cv2
    from djitellopy import Tello
except ImportError:
    sys.exit("Error: Please run 'pip install opencv-python djitellopy'")


def main():
    parser = argparse.ArgumentParser(description="Tello Live Camera Broadcaster")
    parser.add_argument("--ip", default="192.168.10.1", help="Drone IP address (default: 192.168.10.1)")
    args = parser.parse_args()

    drone_ip = args.ip
    print(f"\n{'=' * 60}")
    print(f"CONNECTING TO DRONE CAMERA AT {drone_ip}...")
    print(f"{'=' * 60}\n")

    tello = Tello(host=drone_ip, retry_count=3)
    writer = None
    video_path = None
    try:
        tello.connect(wait_for_state=False)

        # Query and display telemetry
        try:
            bat = tello.get_battery()
            print(f"  * Drone Battery: {bat}%")
        except Exception:
            bat = "N/A"

        print("  * Starting video stream (streamon)...")
        tello.streamon()
        frame_reader = tello.get_frame_read()

        window_name = f"RoboMaster TT Live Camera ({drone_ip})"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 960, 720)

        print("\n" + "=" * 60)
        print("LIVE BROADCASTING ACTIVE")
        print("  * Live video window is now visible on your screen.")
        print("  * Press 'q' or 'ESC' on the window to close.")
        print("  * Press 's' to save a snapshot photo.")
        print("  * Press 'v' to start or stop a video recording.")
        print("=" * 60 + "\n")

        snapshot_idx = 0
        video_idx = 0
        writer = None
        video_path = None
        fps_time = time.time()
        fps_counter = 0
        fps = 0

        while True:
            frame = frame_reader.frame
            if frame is not None and frame.size > 0:
                fps_counter += 1
                if time.time() - fps_time >= 1.0:
                    fps = fps_counter
                    fps_counter = 0
                    fps_time = time.time()

                display = frame.copy()
                if writer is not None:
                    writer.write(frame)
                rec = "REC" if writer is not None else ""
                # Telemetry overlay
                cv2.putText(
                    display,
                    f"RoboMaster TT Live | Bat: {bat}% | FPS: {fps} {rec}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )
                cv2.putText(
                    display,
                    "[q]: Exit | [s]: Snapshot | [v]: Video",
                    (20, display.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    1,
                )
                cv2.imshow(window_name, display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("Exit requested by user.")
                break
            elif key == ord("s") and frame is not None:
                snapshot_idx += 1
                filename = f"RMTT-306E2E_capture_{snapshot_idx}.jpg"
                cv2.imwrite(filename, frame)
                print(f"[Snapshot] Saved {filename}")
            elif key == ord("v") and frame is not None:
                if writer is None:
                    video_idx += 1
                    video_path = f"RMTT-306E2E_video_{video_idx}.mp4"
                    height, width = frame.shape[:2]
                    writer = cv2.VideoWriter(
                        video_path,
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        15.0,
                        (width, height),
                    )
                    print(f"[Video] Recording {video_path}")
                else:
                    writer.release()
                    writer = None
                    print(f"[Video] Saved {video_path}")

    except KeyboardInterrupt:
        print("\nStopping camera stream...")
    except Exception as e:
        print(f"\n[!] Camera error: {e}")
    finally:
        if writer is not None:
            writer.release()
            print(f"[Video] Saved {video_path}")
        try:
            tello.streamoff()
        except Exception:
            pass
        cv2.destroyAllWindows()
        try:
            tello.end()
        except Exception:
            pass
        print("[Done] Camera window closed.")


if __name__ == "__main__":
    main()
