import time
import cv2
import numpy as np
from djitellopy import Tello

# 1. Connect
drone = Tello()
# If using home Wi-Fi: drone = Tello(host="YOUR_DRONE_IP")
drone.connect()
print(f"Battery: {drone.get_battery()}%")

# 2. Start Video Stream
drone.streamon()
time.sleep(1)

frame_read = drone.get_frame_read()
print("Waiting for camera feed...")

start_time = time.time()
valid_frame_found = False

while time.time() - start_time < 10:
    frame = frame_read.frame
    
    if frame is not None and np.mean(frame) > 10:
        valid_frame_found = True
        
        # djitellopy returns RGB; convert to BGR for OpenCV
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        cv2.imwrite("home_wifi_test.jpg", frame_bgr)
        print("📸 SUCCESS! Frame saved as 'home_wifi_test.jpg'")
        break
    
    time.sleep(0.2)

if not valid_frame_found:
    print("❌ ERROR: Could not receive video feed.")

# 3. Clean Shutdown (Prevents WinError 6 on Windows)
try:
    if frame_read is not None:
        frame_read.stop()  # Stop background frame capture thread first
    drone.streamoff()
except Exception as e:
    print(f"Stream closed safely (Ignored cleanup error: {e})")