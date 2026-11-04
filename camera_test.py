import time
import cv2
import threading
from djitellopy import Tello

DRONE_IP = "172.20.10.2"
OUTPUT_FILENAME = "drone_flight_video.avi"
FPS = 20.0
FRAME_WIDTH = 960
FRAME_HEIGHT = 720

# Flag to control the background video recording loop
keep_recording = True

def record_video(drone, output_path):
    global keep_recording
    
    frame_read = drone.get_frame_read()
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_path, fourcc, FPS, (FRAME_WIDTH, FRAME_HEIGHT))

    print("🎥 Video recording thread started...")
    
    while keep_recording:
        frame = frame_read.frame
        if frame is not None and frame.size > 0:
            # Convert DJITelloPy RGB to OpenCV BGR
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            # Ensure frame dimensions strictly match the VideoWriter config
            resized_frame = cv2.resize(frame_bgr, (FRAME_WIDTH, FRAME_HEIGHT))
            out.write(resized_frame)
        time.sleep(1.0 / FPS)
        
    out.release()
    print("⏹️ Video file saved successfully.")

def main():
    global keep_recording

    # 1. Connect to Drone over IP
    drone = Tello(host=DRONE_IP)
    drone.connect()
    print(f"Connected! Battery Level: {drone.get_battery()}%")

    # 2. Initialize Camera Feed
    drone.streamon()
    time.sleep(2)  # Sensor warmup

    # 3. Launch Recording Thread in Background
    recorder_thread = threading.Thread(target=record_video, args=(drone, OUTPUT_FILENAME))
    recorder_thread.daemon = True
    recorder_thread.start()

    try:
        # 4. Flight Sequence
        print("🛫 Taking off...")
        drone.takeoff()
        time.sleep(1)

        print("➡️ Moving forward 30 cm...")
        drone.move_forward(30)
        time.sleep(1)

        print("🔄 Performing 360-degree rotation...")
        drone.rotate_clockwise(360)
        time.sleep(1)

        print("🛬 Landing safely...")
        drone.land()

    except Exception as e:
        print(f"⚠️ Emergency / Error during flight: {e}")
        try:
            drone.land()
        except:
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

        print(f"✨ Done! Check '{OUTPUT_FILENAME}' in your VS Code folder.")

if __name__ == "__main__":
    main()