import time
from djitellopy import Tello

# Pass the exact IP address assigned by your Wi-Fi router
DRONE_IP = "10.37.75.76"  # Assigned IP on Samsung hotspot

drone = Tello(host=DRONE_IP)
drone.connect()

print(f"Connected successfully! Battery level: {drone.get_battery()}%")