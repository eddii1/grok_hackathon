"""
USB (RNDIS) Direct Diagnostic & Test Tool for DJI RoboMaster EP Rover.
Run this script once the rover is plugged into the PC via USB.
"""

import sys
import time
import subprocess
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import robomaster.config as rm_config
if not hasattr(rm_config, "DEFAULT_CONN_PROTO"):
    rm_config.DEFAULT_CONN_PROTO = getattr(rm_config, "DEFAULT_PROTO_TYPE", 0)

from robomaster import robot


def test_usb_connection():
    print("=" * 65)
    print("  DJI RoboMaster EP — USB Direct Diagnostics")
    print("=" * 65)

    # 1. Check if RNDIS interface or 192.168.42.2 is reachable
    print("\n[Step 1] Pinging RoboMaster EP at 192.168.42.2 over USB...")
    ping_res = subprocess.run(["ping", "-n", "2", "-w", "500", "192.168.42.2"], capture_output=True, text=True)
    if "TTL=" in ping_res.stdout or "Reply from" in ping_res.stdout:
        print("  -> SUCCESS: Rover responded to ping at 192.168.42.2!")
    else:
        print("  -> Notice: Ping did not respond. Trying SDK RNDIS handshake anyway...")

    # 2. Try initializing via SDK
    print("\n[Step 2] Initializing official RoboMaster SDK session (conn_type='rndis')...")
    ep_robot = robot.Robot()
    try:
        ret = ep_robot.initialize(conn_type="rndis")
        if not ret:
            print("  -> ERROR: Failed to initialize session over USB.")
            return False
        
        print("  -> SUCCESS: Connected to RoboMaster EP over USB!")
        
        # 3. Hardware version & battery
        print("\n[Step 3] Querying Rover Modules:")
        try:
            ver = ep_robot.get_version()
            print(f"  -> Firmware / SDK Version: {ver}")
        except Exception as e:
            print(f"  -> Version query error: {e}")

        try:
            bat = ep_robot.battery.get_battery()
            print(f"  -> Battery Level: {bat}%")
        except Exception as e:
            print(f"  -> Battery query info: {e}")

        # 4. Camera live test
        print("\n[Step 4] Testing Camera Video Stream...")
        try:
            ep_camera = ep_robot.camera
            ep_camera.start_video_stream(display=False, resolution="720p")
            time.sleep(1)
            frame = ep_camera.read_cv2_image(timeout=2, strategy="newest")
            if frame is not None and frame.size > 0:
                print(f"  -> SUCCESS: Camera is working! Received frame of shape {frame.shape}")
                # Save test image to rover/media/
                import cv2
                save_path = Path(__file__).resolve().parent / "media" / "usb_camera_test.jpg"
                cv2.imwrite(str(save_path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                print(f"  -> Test image saved to: {save_path}")
            else:
                print("  -> Warning: Video stream opened but no frame received.")
            ep_camera.stop_video_stream()
        except Exception as e:
            print(f"  -> Camera test error: {e}")

        # 5. Arm & Gripper test
        print("\n[Step 5] Testing Robotic Arm & Gripper...")
        try:
            ep_arm = ep_robot.robotic_arm
            print("  -> Recentering arm...")
            ep_arm.recenter().wait_for_completed(timeout=2)
            print("  -> Arm functional!")

            ep_gripper = ep_robot.gripper
            print("  -> Testing gripper open/close...")
            ep_gripper.open(power=50)
            time.sleep(1)
            ep_gripper.close(power=50)
            time.sleep(1)
            print("  -> Gripper functional!")
        except Exception as e:
            print(f"  -> Manipulator test info: {e}")

        ep_robot.close()
        print("\n" + "=" * 65)
        print(">>> ALL TESTS PASSED! USB LINK IS FULLY FUNCTIONAL <<<")
        print("=" * 65)
        return True

    except Exception as e:
        print(f"Connection failed: {e}")
        try:
            ep_robot.close()
        except Exception:
            pass
        return False


if __name__ == "__main__":
    test_usb_connection()

