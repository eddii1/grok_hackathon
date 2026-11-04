import time
from djitellopy import Tello

# Pass the exact IP address assigned by your Wi-Fi router
DRONE_IP = "1"  # Replace with the IP found in Step 1

drone = Tello(host=DRONE_IP)
drone.connect()

print(f"Connected successfully! Battery level: {drone.get_battery()}%")