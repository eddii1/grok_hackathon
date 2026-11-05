"""
Flask Web Dashboard Server for DJI RoboMaster EP Rover.
Provides real-time MJPEG camera streaming, snapshot capture, video recording,
virtual remote manual control, Wi-Fi pairing assistant, and media gallery.
"""

import os
import sys
import time
from pathlib import Path
from flask import Flask, render_template, Response, jsonify, request, send_from_directory

# Ensure rover package is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rover.rover_controller import rover_ctrl, MEDIA_DIR

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)

# Ensure media directory exists
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Generate QR code on startup so it is immediately available
rover_ctrl.generate_samsung_qr(ssid="Samsung", password="12345678m")


def gen_frames():
    """Generator for MJPEG video streaming."""
    while True:
        frame_bytes = rover_ctrl.get_stream_frame()
        if frame_bytes:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
        time.sleep(0.033)  # ~30 FPS


@app.route("/")
def index():
    """Main dashboard page."""
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    """MJPEG live camera stream endpoint."""
    return Response(
        gen_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/api/status")
def api_status():
    """Returns rover telemetry, connection state, and storage metrics."""
    return jsonify(rover_ctrl.get_status())


@app.route("/api/wifi/qr")
def api_wifi_qr():
    """Returns the generated Samsung Wi-Fi QR code image."""
    qr_path = Path(__file__).resolve().parent / "samsung_wifi_qr.png"
    if not qr_path.exists():
        rover_ctrl.generate_samsung_qr(ssid="Samsung", password="12345678m")
    return send_from_directory(str(qr_path.parent), qr_path.name)


@app.route("/api/wifi/connect", methods=["POST"])
def api_wifi_connect():
    """Attempts connection to the rover (auto-discovery or manual IP)."""
    data = request.get_json(silent=True) or {}
    target_ip = data.get("ip")
    conn_type = data.get("conn_type", "sta")
    success = rover_ctrl.connect(target_ip=target_ip, conn_type=conn_type)
    return jsonify({
        "success": success,
        "status": rover_ctrl.status,
        "message": rover_ctrl.status_msg,
        "rover_ip": rover_ctrl.rover_ip,
    })


@app.route("/api/wifi/disconnect", methods=["POST"])
def api_wifi_disconnect():
    """Disconnects rover gracefully."""
    rover_ctrl.disconnect()
    return jsonify({"success": True, "status": rover_ctrl.status})


@app.route("/api/camera/restart", methods=["POST"])
def api_camera_restart():
    """Restarts the robot camera video stream."""
    success = rover_ctrl.restart_camera_stream()
    return jsonify({"success": success})


@app.route("/api/debug/stream")
def api_debug_stream():
    """Diagnostic telemetry for live video stream."""
    cam = rover_ctrl.camera
    res = {
        "status": rover_ctrl.status,
        "camera_exists": bool(cam),
        "stream_active": rover_ctrl.stream_active,
        "latest_jpeg_len": len(rover_ctrl.latest_jpeg) if rover_ctrl.latest_jpeg else 0,
    }
    if cam and hasattr(cam, "_liveview"):
        lv = cam._liveview
        res["video_streaming"] = getattr(lv, "_video_streaming", None)
        conn = getattr(lv, "_video_stream_conn", None)
        if conn:
            res["conn_receiving"] = getattr(conn, "_receiving", None)
            res["conn_recv_count"] = getattr(conn, "_recv_count", None)
            res["conn_sock"] = str(getattr(conn, "_sock", None))
        q = getattr(lv, "_video_frame_queue", None)
        if q:
            res["video_queue_qsize"] = q.qsize()
    return jsonify(res)


@app.route("/api/sensor/check")
def api_sensor_check():
    """Checks if ToF proximity distance sensors are present and reading data."""
    if not rover_ctrl.robot:
        return jsonify({"connected": False, "has_sensors": False})
    res = {"connected": True}
    try:
        sensor = rover_ctrl.robot.sensor
        readings = []
        def on_tof(dist):
            readings.append(dist)
        sensor.sub_distance(freq=10, callback=on_tof)
        time.sleep(0.6)
        sensor.unsub_distance()
        res["tof_readings"] = readings[-1] if readings else None
        res["has_sensors"] = bool(readings)
    except Exception as e:
        res["error"] = str(e)
        res["has_sensors"] = False
    return jsonify(res)


@app.route("/api/map/data")
def api_map_data():
    """Returns 2D SLAM room map, obstacle points, trail, and proximity telemetry."""
    return jsonify(rover_ctrl.get_map_data())


@app.route("/api/map/clear", methods=["POST"])
def api_map_clear():
    """Clears room map obstacles and reset trail."""
    success = rover_ctrl.clear_map()
    return jsonify({"success": success})


@app.route("/api/map/toggle_collision", methods=["POST"])
def api_map_toggle_collision():
    """Toggles or sets automated collision avoidance braking."""
    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled", None)
    new_state = rover_ctrl.toggle_collision_avoidance(enabled=enabled)
    return jsonify({"success": True, "collision_avoidance_enabled": new_state})


@app.route("/api/control/drive", methods=["POST"])
def api_control_drive():
    """
    Drives chassis omnidirectionally.
    Expects JSON: { vx: float, vy: float, vz: float }
    """
    data = request.get_json(silent=True) or {}
    vx = float(data.get("vx", 0.0))
    vy = float(data.get("vy", 0.0))
    vz = float(data.get("vz", 0.0))
    success = rover_ctrl.drive(vx=vx, vy=vy, vz=vz)
    return jsonify({"success": success, "speeds": rover_ctrl.current_speeds})


@app.route("/api/control/stop", methods=["POST"])
def api_control_stop():
    """Emergency halt for chassis."""
    rover_ctrl.stop()
    return jsonify({"success": True})


@app.route("/api/control/arm", methods=["POST"])
def api_control_arm():
    """
    Controls robotic arm.
    Expects JSON: { action: "move"|"recenter", x: int, y: int }
    """
    data = request.get_json(silent=True) or {}
    action = data.get("action", "move")
    if action == "recenter":
        success = rover_ctrl.arm_recenter()
    else:
        x = int(data.get("x", 0))
        y = int(data.get("y", 0))
        success = rover_ctrl.arm_move(x=x, y=y)
    return jsonify({"success": success})


@app.route("/api/control/gripper", methods=["POST"])
def api_control_gripper():
    """
    Controls robotic gripper.
    Expects JSON: { action: "open"|"close"|"pause", power: int }
    """
    data = request.get_json(silent=True) or {}
    action = data.get("action", "open")
    power = int(data.get("power", 50))

    if action == "open":
        success = rover_ctrl.gripper_open(power=power)
    elif action == "close":
        success = rover_ctrl.gripper_close(power=power)
    else:
        success = rover_ctrl.gripper_pause()
    return jsonify({"success": success})


@app.route("/api/media/capture", methods=["POST"])
def api_media_capture():
    """Captures a snapshot image and saves it to rover/media/."""
    result = rover_ctrl.capture_image()
    return jsonify(result)


@app.route("/api/media/record/start", methods=["POST"])
def api_media_record_start():
    """Starts recording live stream to rover/media/."""
    result = rover_ctrl.start_recording()
    return jsonify(result)


@app.route("/api/media/record/stop", methods=["POST"])
def api_media_record_stop():
    """Stops live stream recording."""
    result = rover_ctrl.stop_recording()
    return jsonify(result)


@app.route("/api/media/list")
def api_media_list():
    """Returns list of media files stored in rover/media/."""
    return jsonify({"files": rover_ctrl.list_media()})


@app.route("/media/<path:filename>")
def serve_media(filename):
    """Serves media files (images/videos) from rover/media/."""
    return send_from_directory(str(MEDIA_DIR), filename)


@app.route("/api/media/delete/<filename>", methods=["DELETE"])
def api_media_delete(filename):
    """Deletes a file from rover/media/."""
    file_path = MEDIA_DIR / filename
    if file_path.exists() and file_path.is_file():
        try:
            file_path.unlink()
            return jsonify({"success": True, "filename": filename})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"success": False, "message": "File not found"}), 404


if __name__ == "__main__":
    port = 5000
    print(f"\n=======================================================")
    print(f"  RoboMaster EP Rover Dashboard starting on:")
    print(f"  -> Local URL:   http://localhost:{port}")
    print(f"  -> Network URL: http://{rover_ctrl._get_local_wifi_ip()}:{port}")
    print(f"=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

