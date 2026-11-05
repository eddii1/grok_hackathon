"""
RoboMaster EP Rover Controller module.
Handles robot connection, visual QR pairing handshake, camera streaming,
video recording, snapshot capture, chassis/arm/gripper controls, and telemetry.
"""

import os
import sys
import time
import math
import socket
import logging
import threading
import datetime
import queue
from pathlib import Path
import cv2
import numpy as np

# Replace DJI's unsupported native decoder before loading any SDK camera modules.
from rover.sdk_compat import install as install_sdk_compat
install_sdk_compat()

# Apply patch to robomaster config before importing robot/client
import robomaster.config as rm_config
if not hasattr(rm_config, "DEFAULT_CONN_PROTO"):
    rm_config.DEFAULT_CONN_PROTO = getattr(rm_config, "DEFAULT_PROTO_TYPE", 0)

from robomaster import robot, conn, protocol, algo
from rover.sdk_compat import patch_video
patch_video()

logger = logging.getLogger("RoverController")
logging.basicConfig(level=logging.INFO)

MEDIA_DIR = Path(__file__).resolve().parent / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Fixed persistent AppID for QR code pairing handshake
PERSISTENT_APPID = "16888"


class RoverController:
    """Singleton controller managing RoboMaster EP hardware, camera, and state."""

    def __init__(self, media_dir=None):
        self.media_dir = Path(media_dir) if media_dir else MEDIA_DIR
        self.media_dir.mkdir(parents=True, exist_ok=True)

        self.robot = None
        self.chassis = None
        self.camera = None
        self.arm = None
        self.gripper = None
        self.battery = None

        self.status = "DISCONNECTED"  # DISCONNECTED, SCANNING, CONNECTING, CONNECTED, ERROR
        self.status_msg = "Pairing listener active on port 45678. Waiting for rover..."
        self.rover_ip = None
        self.battery_level = 100
        self.sn = "Unknown"

        # Persistent ConnectionHelper
        self.conn_helper = conn.ConnectionHelper()
        self.conn_helper._appid = PERSISTENT_APPID

        # Streaming & frame management
        self.latest_frame = None
        self.latest_jpeg = None
        self.frame_lock = threading.Lock()
        self.stream_active = False
        self.stream_thread = None

        # Recording
        self.is_recording = False
        self.video_writer = None
        self.recording_start_time = None
        self.current_video_file = None
        self.record_lock = threading.Lock()

        # Arm coordinate tracking
        self.arm_x = 130
        self.arm_y = 80

        # Proximity Sensors & 2D SLAM Room Mapping
        self.sensor = None
        self.current_distance_mm = 0
        self.robot_pos = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.robot_yaw = 0.0
        self.map_points = []
        self.map_grid_set = set()
        self.robot_trail = []
        self.map_lock = threading.Lock()
        self.collision_avoidance_enabled = True
        self.collision_warning = False
        self.min_safety_dist_mm = 280  # 28 cm collision warning & auto-brake threshold

        # Motion & Watchdog
        self.last_drive_time = time.time()
        self.current_speeds = {"vx": 0.0, "vy": 0.0, "vz": 0.0}
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog_thread.start()

        # Generate initial QR code image
        self.generate_samsung_qr()

        # Start continuous pairing & discovery listener in background
        self.listener_running = True
        self.listener_thread = threading.Thread(target=self._pairing_listener_loop, daemon=True)
        self.listener_thread.start()

        # Subnet background probe thread
        self.probe_thread = threading.Thread(target=self._subnet_probe_loop, daemon=True)
        self.probe_thread.start()

    # ---------------------------------------------------------
    # Network Discovery & QR Code Pairing Handshake
    # ---------------------------------------------------------

    def generate_samsung_qr(self, ssid="Samsung", password="12345678m"):
        """Generates the official RoboMaster encrypted QR code string and image with persistent AppID."""
        import qrcode
        self.conn_helper._appid = PERSISTENT_APPID
        qr_text = self.conn_helper.build_qrcode_string(ssid=ssid, password=password)
        qr_path = self.media_dir.parent / "samsung_wifi_qr.png"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=3,
        )
        qr.add_data(qr_text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        try:
            img.save(str(qr_path))
        except Exception as e:
            logger.warning(f"Could not overwrite {qr_path} directly ({e}), saving to fallback")
            qr_path = self.media_dir.parent / "samsung_wifi_qr_active.png"
            img.save(str(qr_path))
        logger.info(f"Generated Samsung Wi-Fi QR code saved to {qr_path} (AppID: {PERSISTENT_APPID})")
        return qr_text, str(qr_path)

    def _pairing_listener_loop(self):
        """
        Continuously listens on UDP port 45678 for the RoboMaster EP pairing broadcast.
        CRITICAL: When the rover joins Wi-Fi, it broadcasts its packet and WAITS for
        an immediate ACK reply with its AppID. If no ACK is received, it hums, moves
        left-and-right (shake head fail gesture), and disconnects!
        """
        logger.info("Starting permanent pairing handshake listener on UDP port 45678...")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", 45678))
            s.settimeout(1.0)
        except Exception as e:
            logger.error(f"Failed to bind pairing listener on port 45678: {e}")
            return

        while self.listener_running:
            try:
                data, addr = s.recvfrom(1024)
                if not data or not addr:
                    continue

                logger.info(f"Received {len(data)} bytes UDP broadcast from {addr}")
                rover_ip = addr[0]

                # Decrypt and unpack RoboMaster pairing packet
                decode_buf = algo.simple_encrypt(data)
                conn_info = protocol.STAConnInfo()
                unpacked = conn_info.unpack(decode_buf)

                appid = conn_info._recv_appid if unpacked else PERSISTENT_APPID
                logger.info(f"ROVER BROADCAST RECEIVED! IP: {rover_ip}, AppID: '{appid}'")

                # SEND HANDSHAKE ACK BACK TO ROVER (send 3 times to ensure UDP reception)
                ack_payload = appid.encode("utf-8")
                for _ in range(3):
                    s.sendto(ack_payload, addr)
                    time.sleep(0.05)

                logger.info(f">>> HANDSHAKE ACK SENT TO {addr} (AppID: {appid})! Rover should chime success! <<<")
                
                # Only trigger session if not already connected
                if self.status != "CONNECTED":
                    self.status_msg = f"Handshake ACK sent to {rover_ip}! Initializing session..."
                    threading.Thread(target=self._connect_robot_session, args=(rover_ip,), daemon=True).start()
                else:
                    logger.info(f"Rover handshake broadcast received from {rover_ip}, but session already CONNECTED at {self.rover_ip}")

            except socket.timeout:
                continue
            except Exception as e:
                logger.debug(f"Pairing listener iteration error: {e}")
                time.sleep(0.1)

        s.close()
        logger.info("Pairing listener loop stopped.")

    def _subnet_probe_loop(self):
        """Periodic background probe on 10.37.75.x to find already-connected rovers."""
        time.sleep(3)
        while self.listener_running:
            if self.status not in ["CONNECTED", "CONNECTING"]:
                try:
                    found_ip = self.scan_for_rover_ip(timeout=1.0)
                    if found_ip and self.status not in ["CONNECTED", "CONNECTING"]:
                        logger.info(f"Subnet probe found active rover at {found_ip}")
                        self.status_msg = f"Detected rover at {found_ip}, connecting..."
                        threading.Thread(target=self._connect_robot_session, args=(found_ip,), daemon=True).start()
                except Exception:
                    pass
            time.sleep(5)

    def scan_for_rover_ip(self, timeout=1.0):
        """Scans for active RoboMaster on local subnet ports (40923 / 20020)."""
        local_ip = self._get_local_wifi_ip()
        if not local_ip or local_ip.startswith("127."):
            return None

        prefix = ".".join(local_ip.split(".")[:3]) + "."
        import concurrent.futures

        def probe(ip):
            for port in [40923, 20020]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.12)
                try:
                    sock.connect((ip, port))
                    sock.close()
                    return ip
                except Exception:
                    pass
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(probe, f"{prefix}{i}") for i in range(1, 255)]
            for f in concurrent.futures.as_completed(futures):
                res = f.result()
                if res and res != local_ip:
                    return res
        return None

    def _get_local_wifi_ip(self, target_ip=None):
        """Use the OS route to the robot, including on macOS. UDP connect sends no packet."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect((target_ip or self.rover_ip or "10.255.255.255", 40923))
                ip = probe.getsockname()[0]
                if ip != "0.0.0.0" and not ip.startswith(("127.", "169.254.")):
                    return ip
        except OSError:
            pass
        try:
            import subprocess
            out = subprocess.check_output(
                ["netsh", "interface", "ip", "show", "address", "name=Wi-Fi"],
                text=True,
                errors="replace",
            )
            for line in out.splitlines():
                if "IP Address" in line and ":" in line:
                    ip = line.split(":", 1)[1].strip()
                    if ip and not ip.startswith("169.254."):
                        return ip
        except Exception:
            pass
        return "0.0.0.0"  # no fabricated AP address: connection must report the missing route

    def _get_connected_wifi_ssid(self):
        """Returns the SSID of the currently connected Wi-Fi network."""
        try:
            import subprocess
            out = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                text=True,
                errors="replace",
            )
            for line in out.splitlines():
                if "SSID" in line and "BSSID" not in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        val = parts[1].strip()
                        if val:
                            return val
        except Exception:
            pass
        return "RMEP-2f19a1" if (self.rover_ip == "192.168.2.1") else "Direct AP"

    # ---------------------------------------------------------
    # Robot Session Connection
    # ---------------------------------------------------------

    def connect(self, target_ip=None, conn_type="sta"):
        """Initiates connection to the RoboMaster EP."""
        if self.status == "CONNECTED":
            return True

        if not target_ip:
            target_ip = self.scan_for_rover_ip(timeout=1.5)

        if not target_ip and conn_type == "sta":
            self.status_msg = "Rover not found yet. Please aim camera at QR code and press connect button."
            return False

        threading.Thread(target=self._connect_robot_session, args=(target_ip, conn_type), daemon=True).start()
        return True

    def _connect_robot_session(self, target_ip, conn_type="sta"):
        """Performs actual RoboMaster SDK initialization."""
        if self.status == "CONNECTED":
            return True

        self.status = "CONNECTING"
        wifi_ip = self._get_local_wifi_ip(target_ip)
        if wifi_ip == "0.0.0.0":
            self.status = "ERROR"
            self.status_msg = "No local route to rover. Join its hotspot/network and reconnect."
            return False
        rm_config.LOCAL_IP_STR = wifi_ip  # SDK control/video callbacks must use the reachable Mac address

        if conn_type == "ap":
            conn_type = "ap"
            target_ip = "192.168.2.1"
            rm_config.ROBOT_IP_STR = None
            rm_config.LOCAL_IP_STR = wifi_ip
        elif conn_type == "rndis":
            target_ip = "192.168.42.2"
            rm_config.ROBOT_IP_STR = None
        elif target_ip:
            rm_config.ROBOT_IP_STR = target_ip

        self.status_msg = f"Connecting session to {target_ip} ({conn_type})..."
        self.rover_ip = target_ip
        logger.info(f"Starting RoboMaster SDK session connection to {target_ip} ({conn_type})...")

        try:
            rm_config.DEFAULT_CONN_PROTO = getattr(rm_config, "DEFAULT_PROTO_TYPE", 0)

            ep_robot = robot.Robot()
            init_res = ep_robot.initialize(conn_type=conn_type)
            if not init_res:
                self.status = "ERROR"
                self.status_msg = f"Failed to initialize robot session at {target_ip}"
                logger.error(self.status_msg)
                return False

            self.robot = ep_robot
            self.chassis = ep_robot.chassis
            self.camera = ep_robot.camera
            self.arm = ep_robot.robotic_arm
            self.gripper = ep_robot.gripper
            self.battery = ep_robot.battery

            # Subscribe to battery updates
            try:
                def on_battery(info):
                    self.battery_level = info
                self.battery.sub_battery_info(freq=1, callback=on_battery)
            except Exception:
                pass

            # Start camera stream safely
            logger.info("Checking robot camera feed...")
            try:
                cam_ok = self.camera.start_video_stream(display=False, resolution="720p")
                if cam_ok:
                    self.stream_active = True
                    self.stream_thread = threading.Thread(target=self._stream_capture_loop, daemon=True)
                    self.stream_thread.start()
                    logger.info("Live camera feed streaming successfully!")
                else:
                    logger.warning("Camera did not start stream. Check the 14-pin camera ribbon cable.")
            except Exception as cam_err:
                logger.warning(f"Camera stream exception (check ribbon cable): {cam_err}")

            # Robotic arm is controlled via motion controller host (3, 6)
            self.arm_connected = True
            logger.info("Robotic arm online and ready for control.")

            # Subscribe to proximity distance sensors for 2D room mapping
            try:
                self.sensor = ep_robot.sensor
                def on_distance(dist):
                    if dist and len(dist) > 0:
                        self._process_distance_reading(dist)
                self.sensor.sub_distance(freq=10, callback=on_distance)
                logger.info("ToF distance sensor subscribed at 10Hz.")
            except Exception as e:
                logger.warning(f"Distance sensor sub warning: {e}")

            # Subscribe to chassis position and attitude odometry
            try:
                def on_pos(pos):
                    self._process_position_reading(pos)
                self.chassis.sub_position(cs=1, freq=10, callback=on_pos)

                def on_atti(atti):
                    self._process_attitude_reading(atti)
                self.chassis.sub_attitude(freq=10, callback=on_atti)
                logger.info("Chassis position & attitude odometry subscribed at 10Hz.")
            except Exception as e:
                logger.warning(f"Chassis odometry sub warning: {e}")

            self.status = "CONNECTED"
            self.status_msg = f"CONNECTED ({self.rover_ip} AP Mode)"
            logger.info(f">>> ROBOMASTER EP SUCCESSFULLY CONNECTED AT {self.rover_ip} <<<")
            return True

        except Exception as e:
            logger.error(f"Error connecting robot session: {e}", exc_info=True)
            self.status = "ERROR"
            self.status_msg = f"Connection error: {str(e)}"
            return False

    def disconnect(self):
        """Disconnects safely and releases robot resources."""
        logger.info("Disconnecting rover...")
        self.stop()
        if self.is_recording:
            self.stop_recording()

        self.stream_active = False
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=1.0)

        if self.camera:
            try:
                self.camera.stop_video_stream()
            except Exception:
                pass

        if self.robot:
            try:
                self.robot.close()
            except Exception:
                pass

        self.robot = None
        self.chassis = None
        self.camera = None
        self.arm = None
        self.gripper = None
        self.battery = None
        self.status = "DISCONNECTED"
        self.status_msg = "Disconnected. Pairing listener active on port 45678."
        logger.info("Rover disconnected.")

    # ---------------------------------------------------------
    # Video Streaming & Standby Generator
    # ---------------------------------------------------------

    def _stream_capture_loop(self):
        """Continuously reads frames from EPCamera and encodes to JPEG."""
        logger.info("Live camera capture loop running.")
        time.sleep(0.4)  # Let video socket and H264 decoder thread initialize
        first_frame = False
        reconnects = 0
        while self.stream_active and self.camera:
            vconn = getattr(getattr(self.camera, "_liveview", None), "_video_stream_conn", None)
            if vconn is not None and getattr(vconn, "eof", False):
                if first_frame:
                    reconnects, first_frame = 0, False  # stream had worked: fresh retry budget
                if reconnects >= 5:
                    self.capture_error = f"Video stream ended, gave up after 5 reconnects: {vconn.end_reason}"
                    time.sleep(1.0)
                    continue
                reconnects += 1
                logger.warning(f"{vconn.end_reason}; reconnecting video ({reconnects}/5)")
                time.sleep(2.0)
                self.restart_camera_stream()
                time.sleep(0.4)
                continue
            try:
                img = self.camera.read_cv2_image(timeout=1.0, strategy="newest")
                if img is not None and img.size > 0:
                    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

                    if not first_frame:
                        first_frame = True
                        logger.info(f"First live camera frame acquired: {bgr.shape}")

                    if self.is_recording and self.video_writer:
                        with self.record_lock:
                            if self.video_writer:
                                self.video_writer.write(bgr)

                    ret, jpeg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        with self.frame_lock:
                            self.latest_frame = bgr
                            self.latest_jpeg = jpeg.tobytes()
                            self.frame_time = time.time()
                else:
                    time.sleep(0.01)
            except queue.Empty:
                time.sleep(0.01)
            except Exception as e:
                if getattr(self, "capture_error", "") != str(e):
                    logger.exception("Camera capture failed")
                self.capture_error = str(e)
                time.sleep(0.05)
        logger.info("Live camera capture loop stopped.")

    def restart_camera_stream(self):
        """Restarts the robot camera video stream."""
        if self.camera and self.status == "CONNECTED":
            try:
                self.camera.stop_video_stream()
                time.sleep(0.3)
                ok = self.camera.start_video_stream(display=False, resolution="720p")
                logger.info(f"Camera stream restart result: {ok}")
                return ok
            except Exception as e:
                logger.error(f"Restart camera stream error: {e}")
                return False
        return False

    def get_stream_frame(self):
        """Returns the latest JPEG frame or generates an active HUD standby frame."""
        if self.status == "CONNECTED" and self.latest_jpeg is not None and time.time() - self.frame_time < 3.0:
            with self.frame_lock:
                return self.latest_jpeg

        return self._generate_standby_frame()

    def _generate_standby_frame(self):
        """Renders a futuristic cyber/tactical HUD when rover is not actively streaming."""
        w, h = 1280, 720
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        for y in range(h):
            val = int(12 + 10 * math.sin(y / 100.0))
            frame[y, :] = (val + 5, val + 2, val)

        grid_color = (35, 30, 25)
        for x in range(0, w, 60):
            cv2.line(frame, (x, 0), (x, h), grid_color, 1)
        for y in range(0, h, 60):
            cv2.line(frame, (0, y), (w, y), grid_color, 1)

        c_len = 50
        accent = (220, 180, 50)  # Cyan-Gold in BGR
        pts = [
            [(30, 30), (30 + c_len, 30), (30, 30 + c_len)],
            [(w - 30, 30), (w - 30 - c_len, 30), (w - 30, 30 + c_len)],
            [(30, h - 30), (30 + c_len, h - 30), (30, h - 30 - c_len)],
            [(w - 30, h - 30), (w - 30 - c_len, h - 30), (w - 30, h - 30 - c_len)],
        ]
        for p in pts:
            cv2.line(frame, p[0], p[1], accent, 2)
            cv2.line(frame, p[0], p[2], accent, 2)

        cx, cy = w // 2, h // 2
        t = time.time()
        pulse_r = int(70 + 6 * math.sin(t * 3))
        cv2.circle(frame, (cx, cy), pulse_r, (80, 70, 50), 1)
        cv2.circle(frame, (cx, cy), 8, accent, -1)
        cv2.line(frame, (cx - 100, cy), (cx - 20, cy), accent, 1)
        cv2.line(frame, (cx + 20, cy), (cx + 100, cy), accent, 1)
        cv2.line(frame, (cx, cy - 80), (cx, cy - 20), accent, 1)
        cv2.line(frame, (cx, cy + 20), (cx, cy + 80), accent, 1)

        angle = (t * 2) % (2 * math.pi)
        rx = int(cx + pulse_r * math.cos(angle))
        ry = int(cy + pulse_r * math.sin(angle))
        cv2.line(frame, (cx, cy), (rx, ry), (0, 200, 255), 2)

        title = "DJI ROBOMASTER EP // TACTICAL COMMAND"
        cv2.putText(frame, title, (cx - 270, cy - 120), cv2.FONT_HERSHEY_SIMPLEX, 0.75, accent, 2)

        if self.status == "CONNECTED":
            status_text = "STATUS: ROVER CONNECTED // CAMERA SENSOR OFFLINE"
            stat_color = (0, 255, 120)
            hint = "Check camera cable: Ensure firmly plugged into 'CAMERA' port on controller"
        else:
            status_text = f"STATUS: {self.status}"
            stat_color = (0, 165, 255)
            hint = self.status_msg[:70]

        cv2.putText(frame, status_text, (cx - 240, cy + 115), cv2.FONT_HERSHEY_SIMPLEX, 0.60, stat_color, 2)
        cv2.putText(frame, hint, (cx - 300, cy + 155), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200, 200, 200), 1)

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, f"TIME: {now_str}", (50, 60), cv2.FONT_HERSHEY_PLAIN, 1.2, (200, 200, 200), 1)
        cv2.putText(frame, "VIDEO: 1280x720 30FPS [STANDBY]", (w - 380, 60), cv2.FONT_HERSHEY_PLAIN, 1.2, (200, 200, 200), 1)

        ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        return jpeg.tobytes()

    # ---------------------------------------------------------
    # Snapshot Capture & Video Recording
    # ---------------------------------------------------------

    def capture_image(self):
        """Captures the current frame and saves it to rover/media/."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{timestamp}.jpg"
        save_path = self.media_dir / filename

        with self.frame_lock:
            if self.latest_frame is not None:
                frame_to_save = self.latest_frame.copy()
            else:
                frame_bytes = self._generate_standby_frame()
                nparr = np.frombuffer(frame_bytes, np.uint8)
                frame_to_save = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        cv2.imwrite(str(save_path), frame_to_save)
        logger.info(f"Saved snapshot to {save_path}")
        return {
            "success": True,
            "filename": filename,
            "path": f"/media/{filename}",
            "size_bytes": save_path.stat().st_size,
            "timestamp": timestamp,
        }

    def start_recording(self):
        """Starts recording live stream to an MP4 file in rover/media/."""
        if self.is_recording:
            return {"success": False, "message": "Already recording"}

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.mp4"
        save_path = self.media_dir / filename

        w, h = 1280, 720
        if self.latest_frame is not None:
            h, w = self.latest_frame.shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(save_path), fourcc, 20.0, (w, h))

        if not writer.isOpened():
            logger.error("Failed to open cv2.VideoWriter")
            return {"success": False, "message": "Failed to initialize video encoder"}

        with self.record_lock:
            self.video_writer = writer
            self.is_recording = True
            self.recording_start_time = time.time()
            self.current_video_file = filename

        logger.info(f"Started video recording: {filename}")
        return {
            "success": True,
            "filename": filename,
            "start_time": self.recording_start_time,
        }

    def stop_recording(self):
        """Stops video recording and finalizes MP4 file."""
        if not self.is_recording:
            return {"success": False, "message": "Not recording"}

        with self.record_lock:
            self.is_recording = False
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None

        duration = time.time() - (self.recording_start_time or time.time())
        filename = self.current_video_file
        file_path = self.media_dir / (filename or "")
        size = file_path.stat().st_size if file_path.exists() else 0

        logger.info(f"Stopped recording {filename} (duration: {duration:.1f}s, size: {size} bytes)")
        return {
            "success": True,
            "filename": filename,
            "path": f"/media/{filename}",
            "duration_sec": round(duration, 1),
            "size_bytes": size,
        }

    # ---------------------------------------------------------
    # Manual Remote Control (Chassis, Arm, Gripper)
    # ---------------------------------------------------------

    def drive(self, vx=0.0, vy=0.0, vz=0.0):
        """
        Drives the chassis omnidirectionally.
        vx: forward/backward velocity (-1.5 to 1.5 m/s)
        vy: left/right strafe velocity (-1.5 to 1.5 m/s)
        vz: rotation velocity (-180 to 180 deg/s)
        """
        # Active Automated Collision Avoidance: Stop forward driving if obstacle is within safety threshold
        if self.collision_avoidance_enabled and self.collision_warning and float(vx) > 0:
            logger.warning(f"Obstacle in path ({self.current_distance_mm}mm). Auto-braking forward drive.")
            vx = 0.0

        self.last_drive_time = time.time()
        self.current_speeds = {"vx": vx, "vy": vy, "vz": vz}

        if self.chassis:
            try:
                self.chassis.drive_speed(x=float(vx), y=float(vy), z=float(vz))
                return True
            except Exception as e:
                logger.error(f"Chassis drive_speed error: {e}")
                return False
        return True

    def stop(self):
        """Stops chassis motion immediately."""
        self.current_speeds = {"vx": 0.0, "vy": 0.0, "vz": 0.0}
        if self.chassis:
            try:
                self.chassis.drive_speed(x=0.0, y=0.0, z=0.0)
                self.chassis.stop()
            except Exception as e:
                logger.error(f"Chassis stop error: {e}")
        return True

    def _watchdog_loop(self):
        """Watchdog: automatically halts chassis if no control input for > 0.8s."""
        while True:
            time.sleep(0.15)
            if any(v != 0.0 for v in self.current_speeds.values()):
                if time.time() - self.last_drive_time > 0.8:
                    self.stop()

    def arm_move(self, x=0, y=0):
        """Moves robotic arm by relative offsets within safe physical bounds."""
        if self.arm and self.robot:
            try:
                # Clear any lingering in-progress action to prevent lockouts
                if hasattr(self.robot, "_action_dispatcher"):
                    self.robot._action_dispatcher._in_progress.clear()

                self.arm_x = max(80, min(180, self.arm_x + int(x)))
                self.arm_y = max(50, min(130, self.arm_y + int(y)))
                logger.info(f"Moving arm to absolute (X={self.arm_x}, Y={self.arm_y})")
                self.arm.moveto(x=self.arm_x, y=self.arm_y)
                return True
            except Exception as e:
                logger.error(f"Arm move error: {e}")
                return False
        return True

    def arm_recenter(self):
        """Recenters robotic arm to calibrated home pose (X=130mm, Y=80mm)."""
        if self.arm and self.robot:
            try:
                if hasattr(self.robot, "_action_dispatcher"):
                    self.robot._action_dispatcher._in_progress.clear()

                self.arm_x = 130
                self.arm_y = 80
                logger.info(f"Resetting arm to calibrated home pose (X={self.arm_x}, Y={self.arm_y})")
                self.arm.moveto(x=self.arm_x, y=self.arm_y)
                return True
            except Exception as e:
                logger.error(f"Arm recenter error: {e}")
                return False
        return True

    def gripper_open(self, power=50):
        """Opens robotic gripper."""
        if self.gripper:
            try:
                self.gripper.open(power=int(power))
                return True
            except Exception as e:
                logger.error(f"Gripper open error: {e}")
                return False
        return True

    def gripper_close(self, power=50):
        """Closes robotic gripper."""
        if self.gripper:
            try:
                self.gripper.close(power=int(power))
                return True
            except Exception as e:
                logger.error(f"Gripper close error: {e}")
                return False
        return True

    def gripper_pause(self):
        """Stops gripper motor."""
        if self.gripper:
            try:
                self.gripper.pause()
                return True
            except Exception as e:
                logger.error(f"Gripper pause error: {e}")
                return False
        return True

    # ---------------------------------------------------------
    # 2D SLAM Room Mapping & Sensor Processing
    # ---------------------------------------------------------

    def _process_position_reading(self, pos):
        """Receives chassis position odometry: pos = (x, y, z) in meters."""
        if pos and len(pos) >= 2:
            x, y = float(pos[0]), float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else 0.0
            self.robot_pos = {"x": x, "y": y, "z": z}
            self.pose_time = time.time()

            with self.map_lock:
                if not self.robot_trail:
                    self.robot_trail.append({"x": round(x, 3), "y": round(y, 3), "yaw": round(self.robot_yaw, 1)})
                else:
                    last = self.robot_trail[-1]
                    dist_sq = (x - last["x"]) ** 2 + (y - last["y"]) ** 2
                    if dist_sq > 0.0009:  # > 3 cm movement
                        self.robot_trail.append({"x": round(x, 3), "y": round(y, 3), "yaw": round(self.robot_yaw, 1)})
                        if len(self.robot_trail) > 1200:
                            self.robot_trail.pop(0)

    def _process_attitude_reading(self, atti):
        """Receives chassis attitude: atti = (yaw, pitch, roll) in degrees."""
        if atti and len(atti) > 0:
            self.robot_yaw = round(float(atti[0]), 1)
            self.attitude_time = time.time()

    def _process_distance_reading(self, dist):
        """
        Receives ToF proximity distance array in mm. Port 1 is dist[0].
        Projects obstacle into 2D Cartesian world map using chassis odometry + yaw.
        """
        if not dist or len(dist) == 0:
            return

        d_mm = int(dist[0])
        self.current_distance_mm = d_mm

        # Collision warning evaluation (< 280 mm threshold)
        if 0 < d_mm <= self.min_safety_dist_mm:
            self.collision_warning = True
        else:
            self.collision_warning = False

        # If valid obstacle detection range (between 60 mm and 4000 mm)
        if 60 <= d_mm <= 4000:
            import math
            d_m = d_mm / 1000.0

            # Convert yaw angle to radians
            # Positive yaw is counter-clockwise in RoboMaster
            yaw_rad = math.radians(self.robot_yaw)

            rx = self.robot_pos["x"]
            ry = self.robot_pos["y"]

            # Compute obstacle position in Cartesian world frame
            ox = rx + d_m * math.cos(yaw_rad)
            oy = ry + d_m * math.sin(yaw_rad)

            # Spatial discretization to 4 cm (0.04m) resolution grid to avoid duplication
            grid_key = (round(ox / 0.04), round(oy / 0.04))

            with self.map_lock:
                if grid_key not in self.map_grid_set:
                    self.map_grid_set.add(grid_key)
                    self.map_points.append({
                        "x": round(ox, 3),
                        "y": round(oy, 3),
                        "dist_mm": d_mm,
                        "time": time.time()
                    })
                    # Keep maximum 2000 points for real-time responsiveness
                    if len(self.map_points) > 2000:
                        evicted = self.map_points.pop(0)
                        evicted_key = (round(evicted["x"] / 0.04), round(evicted["y"] / 0.04))
                        self.map_grid_set.discard(evicted_key)

    def get_map_data(self):
        """Returns 2D SLAM room map and proximity telemetry."""
        with self.map_lock:
            all_x = [p["x"] for p in self.map_points] + [self.robot_pos["x"]]
            all_y = [p["y"] for p in self.map_points] + [self.robot_pos["y"]]
            bounds = {
                "min_x": round(min(all_x), 2) if all_x else -1.0,
                "max_x": round(max(all_x), 2) if all_x else 1.0,
                "min_y": round(min(all_y), 2) if all_y else -1.0,
                "max_y": round(max(all_y), 2) if all_y else 1.0,
            }
            bounds["width_m"] = round(bounds["max_x"] - bounds["min_x"], 2)
            bounds["length_m"] = round(bounds["max_y"] - bounds["min_y"], 2)

            return {
                "robot": {
                    "x": round(self.robot_pos["x"], 3),
                    "y": round(self.robot_pos["y"], 3),
                    "z": round(self.robot_pos["z"], 3),
                    "yaw": round(self.robot_yaw, 1),
                },
                "current_distance_mm": self.current_distance_mm,
                "collision_warning": self.collision_warning,
                "collision_avoidance_enabled": self.collision_avoidance_enabled,
                "safety_dist_mm": self.min_safety_dist_mm,
                "obstacle_count": len(self.map_points),
                "obstacles": self.map_points,
                "trail": self.robot_trail,
                "bounds": bounds,
            }

    def clear_map(self):
        """Clears 2D room map obstacles and robot trail."""
        with self.map_lock:
            self.map_points.clear()
            self.map_grid_set.clear()
            self.robot_trail.clear()
            self.robot_trail.append({
                "x": round(self.robot_pos["x"], 3),
                "y": round(self.robot_pos["y"], 3),
                "yaw": round(self.robot_yaw, 1)
            })
        logger.info("2D Room SLAM Map cleared.")
        return True

    def toggle_collision_avoidance(self, enabled=None):
        """Enables or disables automatic collision brake."""
        if enabled is None:
            self.collision_avoidance_enabled = not self.collision_avoidance_enabled
        else:
            self.collision_avoidance_enabled = bool(enabled)
        logger.info(f"Collision avoidance set to: {self.collision_avoidance_enabled}")
        return self.collision_avoidance_enabled

    # ---------------------------------------------------------
    # Status & Media Listing
    # ---------------------------------------------------------

    def get_status(self):
        """Returns comprehensive rover telemetry and state."""
        media_files = list(self.media_dir.glob("*.*"))
        total_size = sum(f.stat().st_size for f in media_files) if media_files else 0

        rec_duration = 0
        if self.is_recording and self.recording_start_time:
            rec_duration = round(time.time() - self.recording_start_time, 1)

        wifi_ssid = self._get_connected_wifi_ssid()
        local_wifi_ip = self._get_local_wifi_ip()

        conn_mode = "Disconnected"
        status_msg = self.status_msg
        if self.status == "CONNECTED":
            if self.rover_ip == "192.168.2.1" or (wifi_ssid and wifi_ssid.startswith("RMEP-")):
                conn_mode = "Direct AP Mode"
                status_msg = f"Connected via Direct Rover Wi-Fi ({wifi_ssid}) at {self.rover_ip}"
            elif self.rover_ip == "192.168.42.2":
                conn_mode = "USB Cable (RNDIS)"
                status_msg = f"Connected via USB RNDIS cable at {self.rover_ip}"
            else:
                conn_mode = f"Router Mode ({wifi_ssid})"
                status_msg = f"Connected to {wifi_ssid} at {self.rover_ip}"

        return {
            "status": self.status,
            "status_msg": status_msg,
            "conn_mode": conn_mode,
            "wifi_ssid": wifi_ssid,
            "local_wifi_ip": local_wifi_ip,
            "rover_ip": self.rover_ip,
            "battery": self.battery_level,
            "arm_connected": getattr(self, "arm_connected", True),
            "is_recording": self.is_recording,
            "recording_duration": rec_duration,
            "current_video": self.current_video_file,
            "media_count": len(media_files),
            "media_storage_bytes": total_size,
            "speeds": self.current_speeds,
            "current_distance_mm": self.current_distance_mm,
            "collision_warning": self.collision_warning,
            "collision_avoidance_enabled": self.collision_avoidance_enabled,
            "obstacle_count": len(self.map_points),
            "robot_pose": {
                "x": round(self.robot_pos["x"], 2),
                "y": round(self.robot_pos["y"], 2),
                "yaw": round(self.robot_yaw, 1),
            },
        }

    def list_media(self):
        """Returns a list of all images and videos stored in rover/media/."""
        files = []
        for p in sorted(self.media_dir.glob("*.*"), key=lambda f: f.stat().st_mtime, reverse=True):
            if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".mp4", ".avi", ".webm"]:
                stat = p.stat()
                files.append({
                    "name": p.name,
                    "url": f"/media/{p.name}",
                    "type": "video" if p.suffix.lower() in [".mp4", ".avi", ".webm"] else "image",
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                })
        return files


# Global singleton controller instance
rover_ctrl = RoverController()
