This rover is the **DJI RoboMaster EP** (specifically configured with the robotic arm and gripper attachment, along with the **RoboMaster Education Expansion Intelligent Controller** shown in the first image).

---

### How to Control It Programmatically

The RoboMaster EP is designed for education and robotics research, supporting control via Python, Scratch, or direct plaintext socket commands.

#### 1. Hardware Connection Options

You can interface with the rover through:

* **Direct Wi-Fi (AP Mode):** Connect your PC directly to the robot's Wi-Fi network using the credentials printed on the controller label:
* **SSID:** `RMEP-2f14e3`
* **Password:** `12341234`


* **Router Mode:** Connect both the robot and your computer to the same local Wi-Fi router (configured via the DJI RoboMaster app).
* **USB / Serial (UART):** Connect via a Micro-USB cable to the intelligent controller or through third-party platforms (Raspberry Pi, Jetson Nano, Arduino) using UART pins.

---

#### 2. Control Using the Official DJI RoboMaster Python SDK

The standard way to program this robot is via the official **`robomaster`** Python SDK.

##### Step A: Install the SDK

```bash
pip install robomaster

```

*(Requires Python 3.6.5+. On Windows/Linux, OpenCV and FFmpeg are typically required for video streaming.)*

##### Step B: Basic Python Control Script

This script initializes connection, moves the omnidirectional chassis, operates the robotic arm, and controls the gripper:

```python
import time
from robomaster import robot

if __name__ == '__main__':
    # Initialize connection to the EP rover
    ep_robot = robot.Robot()
    ep_robot.initialize(conn_type="sta")  # Use "ap" if connected directly to the robot's Wi-Fi

    # Access robot modules
    ep_chassis = ep_robot.chassis
    ep_arm = ep_robot.robotic_arm
    ep_gripper = ep_robot.gripper

    # 1. Drive forward 0.5 meters at 0.3 m/s
    print("Moving forward...")
    ep_chassis.move(x=0.5, y=0, z=0, xy_speed=0.3).wait_for_completed()

    # 2. Rotate 90 degrees counter-clockwise
    print("Rotating...")
    ep_chassis.move(x=0, y=0, z=90, z_speed=45).wait_for_completed()

    # 3. Control the robotic arm (relative coordinate movement in mm)
    print("Moving robotic arm...")
    ep_arm.moveto(x=150, y=100).wait_for_completed()

    # 4. Open and close the gripper
    print("Opening gripper...")
    ep_gripper.open(power=50)
    time.sleep(2)
    print("Closing gripper...")
    ep_gripper.close(power=50)
    time.sleep(2)

    # Clean up and release control
    ep_robot.close()

```

---

#### 3. Low-Level Control via Plaintext Socket (Plain TCP/UDP)

If you want to use ROS, C++, or another language without the SDK, the EP provides an open plaintext protocol over TCP port `10607`:

1. Connect via TCP to port `10607` on the robot's IP (default in AP mode is `192.168.2.1`).
2. Send `command;` to enter SDK mode.
3. Send plain commands, such as:
* `chassis speed x 0.2 y 0 z 0;` (drive forward)
* `robotic_arm moveto x 100 y 50;` (move arm)
* `robotic_gripper open 1;` (open gripper)



---

#### 4. Visual Block Programming

If you want a no-code/low-code setup, download the **DJI RoboMaster App** on your PC/Mac/tablet, connect to the robot, and go to the **Lab** section to build programs using Scratch blocks or the in-app Python editor.