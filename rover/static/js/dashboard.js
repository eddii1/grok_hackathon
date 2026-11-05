/**
 * DJI RoboMaster EP Rover — Mission Command Dashboard JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
  // --- STATE ---
  const state = {
    status: 'DISCONNECTED',
    roverIp: null,
    battery: 100,
    isRecording: false,
    recDuration: 0,
    driveSpeed: 0.5,
    turnSpeed: 45,
    activeKeys: new Set(),
    driveInterval: null,
    keyboardEnabled: true,
    gripperState: 'open',
    currentFilter: 'all',
    activeModalFile: null,
    viewMode: 'camera', // camera, map, split
    mapZoom: 75,
    mapPan: { x: 0, y: 0 },
    tabMapZoom: 85,
    tabMapPan: { x: 0, y: 0 },
    isDraggingMap: false,
    dragStart: { x: 0, y: 0 },
    isDraggingTabMap: false,
    tabDragStart: { x: 0, y: 0 },
    mapData: null,
    collisionAvoidanceEnabled: true,
  };

  // --- DOM ELEMENTS ---
  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');
  const connStatusPill = document.getElementById('connStatusPill');
  const roverIpEl = document.getElementById('roverIp');
  const wifiSsidEl = document.getElementById('wifiSsid');
  const batteryBar = document.getElementById('batteryBar');
  const batteryText = document.getElementById('batteryText');
  const recPill = document.getElementById('recPill');
  const recTimer = document.getElementById('recTimer');
  const hudTimestamp = document.getElementById('hudTimestamp');
  const hudSpeeds = document.getElementById('hudSpeeds');
  const hudRecordingTag = document.getElementById('hudRecordingTag');
  const cameraFlash = document.getElementById('cameraFlash');

  // Top Nav Proximity Pill
  const proximityPill = document.getElementById('proximityPill');
  const proximityDot = document.getElementById('proximityDot');
  const hudDistance = document.getElementById('hudDistance');

  // View Mode Switcher Elements
  const viewportWrapper = document.getElementById('viewportWrapper');
  const videoContainer = document.getElementById('videoContainer');
  const slamMapContainer = document.getElementById('slamMapContainer');
  const slamCanvas = document.getElementById('slamCanvas');
  const tabSlamCanvas = document.getElementById('tabSlamCanvas');
  const viewModeBadge = document.getElementById('viewModeBadge');
  const viewModeTitle = document.getElementById('viewModeTitle');
  const btnModeCam = document.getElementById('btnModeCam');
  const btnModeMap = document.getElementById('btnModeMap');
  const btnModeSplit = document.getElementById('btnModeSplit');

  // Map Quick Controls Overlay
  const mapPoseHud = document.getElementById('mapPoseHud');
  const mapYawHud = document.getElementById('mapYawHud');
  const mapObstacleCountHud = document.getElementById('mapObstacleCountHud');
  const mapDistanceHud = document.getElementById('mapDistanceHud');
  const mapCollisionAlertHud = document.getElementById('mapCollisionAlertHud');
  const mapDimensionHud = document.getElementById('mapDimensionHud');
  const btnMapZoomIn = document.getElementById('btnMapZoomIn');
  const btnMapZoomOut = document.getElementById('btnMapZoomOut');
  const btnMapCenter = document.getElementById('btnMapCenter');
  const btnMapClear = document.getElementById('btnMapClear');
  const btnToggleBrake = document.getElementById('btnToggleBrake');

  // Tab 4 Elements
  const mapPointsBadge = document.getElementById('mapPointsBadge');
  const tabDistanceVal = document.getElementById('tabDistanceVal');
  const tabDistanceCmVal = document.getElementById('tabDistanceCmVal');
  const tabProximityBar = document.getElementById('tabProximityBar');
  const tabBrakeAlert = document.getElementById('tabBrakeAlert');
  const tabPoseX = document.getElementById('tabPoseX');
  const tabPoseY = document.getElementById('tabPoseY');
  const tabPoseYaw = document.getElementById('tabPoseYaw');
  const tabTrailCount = document.getElementById('tabTrailCount');
  const tabObstaclesCount = document.getElementById('tabObstaclesCount');
  const tabRoomWidth = document.getElementById('tabRoomWidth');
  const tabRoomLength = document.getElementById('tabRoomLength');
  const btnTabZoomIn = document.getElementById('btnTabZoomIn');
  const btnTabZoomOut = document.getElementById('btnTabZoomOut');
  const btnTabCenter = document.getElementById('btnTabCenter');
  const btnTabClear = document.getElementById('btnTabClear');
  const btnTabToggleBrake = document.getElementById('btnTabToggleBrake');

  // Network Details in Settings Tab
  const netDetailSsid = document.getElementById('netDetailSsid');
  const netDetailRoverIp = document.getElementById('netDetailRoverIp');
  const netDetailLocalIp = document.getElementById('netDetailLocalIp');
  const netDetailSwitchMode = document.getElementById('netDetailSwitchMode');
  const activeConnModeBadge = document.getElementById('activeConnModeBadge');

  // Buttons
  const btnCapture = document.getElementById('btnCapture');
  const btnRecord = document.getElementById('btnRecord');
  const recordBtnLabel = document.getElementById('recordBtnLabel');
  const btnFullscreen = document.getElementById('btnFullscreen');
  const btnEmergencyStop = document.getElementById('btnEmergencyStop');
  const kbToggle = document.getElementById('kbToggle');

  // Sliders
  const driveSpeedRange = document.getElementById('driveSpeedRange');
  const driveSpeedVal = document.getElementById('driveSpeedVal');
  const turnSpeedRange = document.getElementById('turnSpeedRange');
  const turnSpeedVal = document.getElementById('turnSpeedVal');

  // Wi-Fi Pairing
  const btnAutoConnect = document.getElementById('btnAutoConnect');
  const btnUsbConnect = document.getElementById('btnUsbConnect');
  const btnManualConnect = document.getElementById('btnManualConnect');
  const btnDisconnect = document.getElementById('btnDisconnect');
  const manualIpInput = document.getElementById('manualIpInput');
  const wifiStatusAlert = document.getElementById('wifiStatusAlert');

  // Gallery
  const mediaGrid = document.getElementById('mediaGrid');
  const mediaCountBadge = document.getElementById('mediaCountBadge');
  const galleryStats = document.getElementById('galleryStats');
  const btnRefreshGallery = document.getElementById('btnRefreshGallery');
  const filterBtns = document.querySelectorAll('.filter-btn');

  // Modal
  const mediaModal = document.getElementById('mediaModal');
  const modalTitle = document.getElementById('modalTitle');
  const modalBody = document.getElementById('modalBody');
  const modalClose = document.getElementById('modalClose');
  const modalDownloadBtn = document.getElementById('modalDownloadBtn');
  const modalDeleteBtn = document.getElementById('modalDeleteBtn');

  // Logs
  const logStream = document.getElementById('logStream');
  const btnClearLogs = document.getElementById('btnClearLogs');

  // -------------------------------------------------------------
  // LOGGING UTILITY
  // -------------------------------------------------------------
  function log(msg, type = 'info') {
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.textContent = `[${time}] ${msg}`;
    logStream.appendChild(line);
    logStream.scrollTop = logStream.scrollHeight;
  }

  btnClearLogs.addEventListener('click', () => {
    logStream.innerHTML = '';
  });

  // -------------------------------------------------------------
  // HUD CLOCK
  // -------------------------------------------------------------
  setInterval(() => {
    const now = new Date();
    hudTimestamp.textContent = now.toISOString().replace('T', ' ').slice(0, 19);
  }, 1000);

  // -------------------------------------------------------------
  // STATUS POLLING
  // -------------------------------------------------------------
  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      if (!res.ok) return;
      const data = await res.json();

      state.status = data.status;
      state.roverIp = data.rover_ip;
      state.battery = data.battery;
      state.isRecording = data.is_recording;
      state.recDuration = data.recording_duration;

      // Update UI
      statusText.textContent = data.status;
      connStatusPill.className = `metric-pill status-pill ${data.status.toLowerCase()}`;
      roverIpEl.textContent = data.rover_ip || '--.---.---.---';
      batteryText.textContent = `${data.battery}%`;
      batteryBar.style.width = `${Math.max(0, Math.min(100, data.battery))}%`;

      // Update Wi-Fi and Network telemetry
      const displaySsid = data.wifi_ssid || (data.rover_ip === '192.168.2.1' ? 'RMEP-2f19a1' : '--');
      if (wifiSsidEl) {
        wifiSsidEl.textContent = displaySsid;
      }

      if (netDetailSsid) netDetailSsid.textContent = displaySsid;
      if (netDetailRoverIp) netDetailRoverIp.textContent = data.rover_ip || '--.---.---.---';
      if (netDetailLocalIp) netDetailLocalIp.textContent = data.local_wifi_ip || '--.---.---.---';
      if (activeConnModeBadge) {
        activeConnModeBadge.textContent = data.conn_mode ? data.conn_mode.toUpperCase() : (data.status === 'CONNECTED' ? 'CONNECTED' : 'OFFLINE');
        if (data.status === 'CONNECTED') {
          activeConnModeBadge.className = 'badge badge-success';
        } else {
          activeConnModeBadge.className = 'badge';
          activeConnModeBadge.style.color = 'var(--text-muted)';
        }
      }
      if (netDetailSwitchMode) {
        if (data.rover_ip === '192.168.2.1' || (displaySsid && displaySsid.startsWith('RMEP-'))) {
          netDetailSwitchMode.textContent = 'Direct Wi-Fi Mode (Phone icon)';
        } else if (data.rover_ip === '192.168.42.2') {
          netDetailSwitchMode.textContent = 'USB RNDIS Mode';
        } else {
          netDetailSwitchMode.textContent = 'Router Mode (Networked squares icon)';
        }
      }

      if (wifiStatusAlert && data.status_msg) {
        wifiStatusAlert.textContent = data.status_msg;
        if (data.status === 'CONNECTED') {
          wifiStatusAlert.style.borderColor = 'var(--accent-green)';
          wifiStatusAlert.style.color = 'var(--accent-green)';
        } else if (data.status === 'CONNECTING' || data.status === 'SCANNING') {
          wifiStatusAlert.style.borderColor = 'var(--accent-gold)';
          wifiStatusAlert.style.color = 'var(--accent-gold)';
        }
      }

      if (data.battery < 20) {
        batteryBar.style.backgroundColor = 'var(--accent-red)';
      } else if (data.battery < 50) {
        batteryBar.style.backgroundColor = 'var(--accent-gold)';
      } else {
        batteryBar.style.backgroundColor = 'var(--accent-green)';
      }

      // Recording State
      if (data.is_recording) {
        recPill.style.display = 'flex';
        hudRecordingTag.style.display = 'inline';
        const mins = String(Math.floor(data.recording_duration / 60)).padStart(2, '0');
        const secs = String(Math.floor(data.recording_duration % 60)).padStart(2, '0');
        recTimer.textContent = `${mins}:${secs}`;
        btnRecord.classList.add('recording');
        recordBtnLabel.textContent = 'STOP RECORDING';
      } else {
        recPill.style.display = 'none';
        hudRecordingTag.style.display = 'none';
        btnRecord.classList.remove('recording');
        recordBtnLabel.textContent = 'START RECORDING';
      }

      // Speeds
      if (data.speeds) {
        hudSpeeds.textContent = `VX: ${data.speeds.vx.toFixed(1)} | VY: ${data.speeds.vy.toFixed(1)} | VZ: ${data.speeds.vz.toFixed(1)}`;
      }

      // Proximity & Collision Alert in Nav
      if (proximityPill && hudDistance) {
        const d = data.current_distance_mm || 0;
        if (d > 0 && d <= 4000) {
          hudDistance.textContent = `${d} mm`;
          if (data.collision_warning) {
            proximityPill.className = 'metric-pill proximity-pill warning';
            hudDistance.textContent = `${d} mm [HAZARD]`;
          } else {
            proximityPill.className = 'metric-pill proximity-pill';
          }
        } else {
          hudDistance.textContent = 'CLEAR';
          proximityPill.className = 'metric-pill proximity-pill';
        }
      }

      // Robotic Arm Detection Notice
      const armSub = document.getElementById('armStatusSubtitle');
      if (armSub) {
        if (data.arm_connected === false) {
          armSub.innerHTML = '<span style="color:var(--accent-red);font-weight:bold;">ARM SERVO BUS DISCONNECTED</span> &bull; Check 4-pin cable';
        } else if (data.status === 'CONNECTED') {
          armSub.textContent = 'MANIPULATOR \u2022 2-AXIS + CLAW (ONLINE)';
        }
      }

      mediaCountBadge.textContent = data.media_count || 0;
    } catch (e) {
      // Server maybe busy
    }
  }

  setInterval(fetchStatus, 1000);
  fetchStatus();

  // -------------------------------------------------------------
  // 2D ROOM SLAM MAP & RADAR RENDERING
  // -------------------------------------------------------------

  function renderMapOnCanvas(canvas, zoom, pan) {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const w = rect.width;
    const h = rect.height;
    if (w === 0 || h === 0) return;

    if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
    }

    const ctx = canvas.getContext('2d');
    ctx.save();
    ctx.scale(dpr, dpr);

    // Deep space tactical radar background
    ctx.fillStyle = '#060d19';
    ctx.fillRect(0, 0, w, h);

    const cx = w / 2 + pan.x;
    const cy = h / 2 + pan.y;

    // Minor grid 0.5m
    const minorStep = 0.5 * zoom;
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(20, 45, 75, 0.4)';
    ctx.beginPath();
    const startX = (cx % minorStep) - minorStep;
    for (let x = startX; x < w; x += minorStep) {
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
    }
    const startY = (cy % minorStep) - minorStep;
    for (let y = startY; y < h; y += minorStep) {
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
    }
    ctx.stroke();

    // Major grid 1.0m
    const majorStep = 1.0 * zoom;
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.12)';
    ctx.beginPath();
    const mStartX = (cx % majorStep) - majorStep;
    for (let x = mStartX; x < w; x += majorStep) {
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
    }
    const mStartY = (cy % majorStep) - majorStep;
    for (let y = mStartY; y < h; y += majorStep) {
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
    }
    ctx.stroke();

    // Concentric Range Rings (1m, 2m, 3m, 4m)
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.18)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    for (let r = 1; r <= 4; r++) {
      const radius = r * zoom;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.stroke();

      ctx.fillStyle = 'rgba(0, 240, 255, 0.4)';
      ctx.font = '10px monospace';
      ctx.fillText(`${r}m`, cx + 4, cy - radius + 11);
    }
    ctx.setLineDash([]);

    // Center Crosshair Axes
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.3)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(cx, 0);
    ctx.lineTo(cx, h);
    ctx.moveTo(0, cy);
    ctx.lineTo(w, cy);
    ctx.stroke();

    const mapData = state.mapData;
    if (!mapData) {
      ctx.restore();
      return;
    }

    // Draw Robot Trail
    if (mapData.trail && mapData.trail.length > 1) {
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(0, 240, 255, 0.45)';
      ctx.lineWidth = 2;
      for (let i = 0; i < mapData.trail.length; i++) {
        const pt = mapData.trail[i];
        const px = cx + pt.x * zoom;
        const py = cy - pt.y * zoom;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.stroke();
    }

    // Draw Mapped Obstacle Points
    if (mapData.obstacles && mapData.obstacles.length > 0) {
      const now = Date.now() / 1000;
      for (let i = 0; i < mapData.obstacles.length; i++) {
        const obs = mapData.obstacles[i];
        const ox = cx + obs.x * zoom;
        const oy = cy - obs.y * zoom;

        const age = now - (obs.time || now);
        if (age < 2.0) {
          ctx.fillStyle = '#ffb800'; // Fresh hit in amber
          ctx.shadowColor = '#ffb800';
          ctx.shadowBlur = 6;
        } else {
          ctx.fillStyle = '#00f0ff';
          ctx.shadowBlur = 0;
        }

        ctx.fillRect(ox - 3, oy - 3, 6, 6);
      }
      ctx.shadowBlur = 0;
    }

    // Draw Robot Pose & Directional Glyph
    const r = mapData.robot || { x: 0, y: 0, yaw: 0 };
    const rx = cx + r.x * zoom;
    const ry = cy - r.y * zoom;
    const yawRad = (r.yaw * Math.PI) / 180.0;

    ctx.save();
    ctx.translate(rx, ry);
    // Rotate by -yawRad (since canvas Y is downwards)
    ctx.rotate(-yawRad);

    // Dynamic ToF Sensor Beam Cone
    const distM = (mapData.current_distance_mm || 0) / 1000.0;
    if (distM > 0.05 && distM < 4.0) {
      const beamLen = distM * zoom;
      const beamAngle = 0.22; // ~25 deg cone
      const grad = ctx.createRadialGradient(0, 0, 5, 0, 0, beamLen);

      if (mapData.collision_warning) {
        grad.addColorStop(0, 'rgba(255, 51, 102, 0.7)');
        grad.addColorStop(1, 'rgba(255, 51, 102, 0.05)');
        ctx.fillStyle = grad;
        ctx.strokeStyle = 'rgba(255, 51, 102, 0.8)';
      } else {
        grad.addColorStop(0, 'rgba(0, 240, 255, 0.35)');
        grad.addColorStop(1, 'rgba(0, 240, 255, 0.02)');
        ctx.fillStyle = grad;
        ctx.strokeStyle = 'rgba(0, 240, 255, 0.5)';
      }

      ctx.beginPath();
      ctx.moveTo(18, 0);
      ctx.lineTo(beamLen * Math.cos(beamAngle), -beamLen * Math.sin(beamAngle));
      ctx.arc(0, 0, beamLen, -beamAngle, beamAngle);
      ctx.closePath();
      ctx.fill();

      // Laser center line
      ctx.beginPath();
      ctx.moveTo(18, 0);
      ctx.lineTo(beamLen, 0);
      ctx.stroke();

      // Laser impact point blip
      ctx.beginPath();
      ctx.arc(beamLen, 0, 4, 0, Math.PI * 2);
      ctx.fillStyle = mapData.collision_warning ? '#ff3366' : '#00ff88';
      ctx.fill();
    }

    // Mecanum Rover Chassis Footprint
    const rw = 24; // Half-width
    const rl = 32; // Half-length
    ctx.fillStyle = '#0e223d';
    ctx.strokeStyle = mapData.collision_warning ? '#ff3366' : '#00f0ff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(-rl, -rw, rl * 2, rw * 2, 6);
    ctx.fill();
    ctx.stroke();

    // 4 Mecanum Rollers
    ctx.fillStyle = '#223856';
    ctx.fillRect(-rl + 2, -rw - 4, 15, 5);
    ctx.fillRect(rl - 17, -rw - 4, 15, 5);
    ctx.fillRect(-rl + 2, rw - 1, 15, 5);
    ctx.fillRect(rl - 17, rw - 1, 15, 5);

    // Front Robotic Arm & Clamp representation
    ctx.strokeStyle = '#00ff88';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(rl, -7);
    ctx.lineTo(rl + 10, -7);
    ctx.moveTo(rl, 7);
    ctx.lineTo(rl + 10, 7);
    ctx.stroke();

    // Forward Direction Arrow
    ctx.fillStyle = '#00f0ff';
    ctx.beginPath();
    ctx.moveTo(10, 0);
    ctx.lineTo(-6, -6);
    ctx.lineTo(-2, 0);
    ctx.lineTo(-6, 6);
    ctx.closePath();
    ctx.fill();

    ctx.restore();
    ctx.restore();
  }

  // -------------------------------------------------------------
  // MAP DATA POLLING & HUD UPDATES
  // -------------------------------------------------------------

  async function pollMapData() {
    try {
      const res = await fetch('/api/map/data');
      if (!res.ok) return;
      const data = await res.json();
      state.mapData = data;
      state.collisionAvoidanceEnabled = data.collision_avoidance_enabled;

      // Update Map HUD Overlay in CAM-01 card
      if (mapPoseHud && data.robot) {
        mapPoseHud.textContent = `POSE: X: ${data.robot.x.toFixed(2)}m | Y: ${data.robot.y.toFixed(2)}m`;
      }
      if (mapYawHud && data.robot) {
        mapYawHud.textContent = `HEADING: ${data.robot.yaw.toFixed(1)}\u00B0`;
      }
      if (mapObstacleCountHud) {
        mapObstacleCountHud.textContent = `OBSTACLES: ${data.obstacle_count} PTS`;
      }
      if (mapDistanceHud) {
        mapDistanceHud.textContent = data.current_distance_mm > 0 ? `RANGE: ${data.current_distance_mm} mm` : 'RANGE: --';
      }
      if (mapCollisionAlertHud) {
        mapCollisionAlertHud.style.display = data.collision_warning ? 'inline' : 'none';
      }
      if (mapDimensionHud && data.bounds) {
        mapDimensionHud.textContent = `ROOM EST: ${data.bounds.length_m} x ${data.bounds.width_m} m`;
      }

      // Update Tab 4 Stats
      if (mapPointsBadge) {
        mapPointsBadge.textContent = `${data.obstacle_count} pts`;
      }
      if (tabDistanceVal) {
        tabDistanceVal.textContent = data.current_distance_mm > 0 ? data.current_distance_mm : '--';
      }
      if (tabDistanceCmVal) {
        tabDistanceCmVal.textContent = data.current_distance_mm > 0 ? `(${Math.round(data.current_distance_mm / 10)} cm)` : '(-- cm)';
      }
      if (tabProximityBar) {
        const pct = Math.min(100, Math.max(0, (4000 - data.current_distance_mm) / 40));
        tabProximityBar.style.width = data.current_distance_mm > 0 ? `${pct}%` : '0%';
      }
      if (tabBrakeAlert) {
        tabBrakeAlert.style.display = data.collision_warning ? 'block' : 'none';
      }
      if (tabPoseX && data.robot) {
        tabPoseX.textContent = `${data.robot.x.toFixed(2)} m`;
      }
      if (tabPoseY && data.robot) {
        tabPoseY.textContent = `${data.robot.y.toFixed(2)} m`;
      }
      if (tabPoseYaw && data.robot) {
        tabPoseYaw.textContent = `${data.robot.yaw.toFixed(1)}\u00B0`;
      }
      if (tabTrailCount && data.trail) {
        tabTrailCount.textContent = data.trail.length;
      }
      if (tabObstaclesCount) {
        tabObstaclesCount.textContent = `${data.obstacle_count} pts`;
      }
      if (tabRoomWidth && data.bounds) {
        tabRoomWidth.textContent = `${data.bounds.width_m} m`;
      }
      if (tabRoomLength && data.bounds) {
        tabRoomLength.textContent = `${data.bounds.length_m} m`;
      }

      // Render visible canvas(es)
      if (state.viewMode === 'map' || state.viewMode === 'split') {
        renderMapOnCanvas(slamCanvas, state.mapZoom, state.mapPan);
      }

      const tabMapPane = document.getElementById('tabMap');
      if (tabMapPane && tabMapPane.classList.contains('active')) {
        renderMapOnCanvas(tabSlamCanvas, state.tabMapZoom, state.tabMapPan);
      }
    } catch (e) {
      // Map poll error
    }
  }

  // Poll 2D map at 5 Hz (every 200ms)
  setInterval(pollMapData, 200);

  // -------------------------------------------------------------
  // VIEW MODE SWITCHER (CAMERA / 2D MAP / SPLIT)
  // -------------------------------------------------------------

  function setViewMode(mode) {
    state.viewMode = mode;
    [btnModeCam, btnModeMap, btnModeSplit].forEach(btn => btn && btn.classList.remove('active'));

    if (mode === 'camera') {
      if (btnModeCam) btnModeCam.classList.add('active');
      viewportWrapper.className = 'viewport-wrapper';
      videoContainer.style.display = 'flex';
      slamMapContainer.style.display = 'none';
      if (viewModeBadge) viewModeBadge.textContent = 'CAM-01';
      if (viewModeTitle) viewModeTitle.textContent = 'PRIMARY OPTICAL SENSOR';
    } else if (mode === 'map') {
      if (btnModeMap) btnModeMap.classList.add('active');
      viewportWrapper.className = 'viewport-wrapper';
      videoContainer.style.display = 'none';
      slamMapContainer.style.display = 'flex';
      if (viewModeBadge) viewModeBadge.textContent = 'SLAM-2D';
      if (viewModeTitle) viewModeTitle.textContent = '2D ROOM RADAR MAP';
      renderMapOnCanvas(slamCanvas, state.mapZoom, state.mapPan);
    } else if (mode === 'split') {
      if (btnModeSplit) btnModeSplit.classList.add('active');
      viewportWrapper.className = 'viewport-wrapper mode-split';
      videoContainer.style.display = 'flex';
      slamMapContainer.style.display = 'flex';
      if (viewModeBadge) viewModeBadge.textContent = 'DUAL-VIEW';
      if (viewModeTitle) viewModeTitle.textContent = 'OPTICAL & RADAR SLAM';
      renderMapOnCanvas(slamCanvas, state.mapZoom, state.mapPan);
    }
  }

  if (btnModeCam) btnModeCam.addEventListener('click', () => setViewMode('camera'));
  if (btnModeMap) btnModeMap.addEventListener('click', () => setViewMode('map'));
  if (btnModeSplit) btnModeSplit.addEventListener('click', () => setViewMode('split'));

  // -------------------------------------------------------------
  // MAP CANVAS PAN & ZOOM INTERACTION
  // -------------------------------------------------------------

  function setupCanvasInteraction(canvas, zoomKey, panKey) {
    if (!canvas) return;

    // Zoom on Wheel
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
      state[zoomKey] = Math.max(25, Math.min(300, state[zoomKey] * zoomFactor));
      renderMapOnCanvas(canvas, state[zoomKey], state[panKey]);
    }, { passive: false });

    // Drag to Pan
    let isDragging = false;
    let startX = 0;
    let startY = 0;

    canvas.addEventListener('mousedown', (e) => {
      isDragging = true;
      startX = e.clientX - state[panKey].x;
      startY = e.clientY - state[panKey].y;
      canvas.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      state[panKey].x = e.clientX - startX;
      state[panKey].y = e.clientY - startY;
      renderMapOnCanvas(canvas, state[zoomKey], state[panKey]);
    });

    window.addEventListener('mouseup', () => {
      if (isDragging) {
        isDragging = false;
        canvas.style.cursor = 'crosshair';
      }
    });

    // Touch support
    let touchStartX = 0;
    let touchStartY = 0;
    canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        touchStartX = e.touches[0].clientX - state[panKey].x;
        touchStartY = e.touches[0].clientY - state[panKey].y;
      }
    });
    canvas.addEventListener('touchmove', (e) => {
      if (e.touches.length === 1) {
        state[panKey].x = e.touches[0].clientX - touchStartX;
        state[panKey].y = e.touches[0].clientY - touchStartY;
        renderMapOnCanvas(canvas, state[zoomKey], state[panKey]);
      }
    });
  }

  setupCanvasInteraction(slamCanvas, 'mapZoom', 'mapPan');
  setupCanvasInteraction(tabSlamCanvas, 'tabMapZoom', 'tabMapPan');

  // Map Controls: Zoom, Center, Clear, Toggle Brake
  if (btnMapZoomIn) {
    btnMapZoomIn.addEventListener('click', () => {
      state.mapZoom = Math.min(300, state.mapZoom * 1.25);
      renderMapOnCanvas(slamCanvas, state.mapZoom, state.mapPan);
    });
  }
  if (btnMapZoomOut) {
    btnMapZoomOut.addEventListener('click', () => {
      state.mapZoom = Math.max(25, state.mapZoom * 0.8);
      renderMapOnCanvas(slamCanvas, state.mapZoom, state.mapPan);
    });
  }
  if (btnMapCenter) {
    btnMapCenter.addEventListener('click', () => {
      if (state.mapData && state.mapData.robot) {
        state.mapPan.x = -state.mapData.robot.x * state.mapZoom;
        state.mapPan.y = state.mapData.robot.y * state.mapZoom;
      } else {
        state.mapPan = { x: 0, y: 0 };
      }
      renderMapOnCanvas(slamCanvas, state.mapZoom, state.mapPan);
    });
  }
  if (btnMapClear) {
    btnMapClear.addEventListener('click', async () => {
      if (!confirm('Clear all mapped obstacle points and movement trail?')) return;
      await fetch('/api/map/clear', { method: 'POST' });
      log('Cleared 2D room map.', 'warn');
      pollMapData();
    });
  }

  async function toggleBraking() {
    const nextState = !state.collisionAvoidanceEnabled;
    try {
      const res = await fetch('/api/map/toggle_collision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: nextState })
      });
      const data = await res.json();
      state.collisionAvoidanceEnabled = data.collision_avoidance_enabled;
      updateBrakeButtons();
      log(`Automated collision brake ${state.collisionAvoidanceEnabled ? 'ENABLED' : 'DISABLED'}.`, 'info');
    } catch (e) {
      log(`Error toggling brake: ${e}`, 'error');
    }
  }

  function updateBrakeButtons() {
    const on = state.collisionAvoidanceEnabled;
    [btnToggleBrake, btnTabToggleBrake].forEach(btn => {
      if (!btn) return;
      if (on) {
        btn.textContent = 'BRAKE: ON';
        btn.className = btn.id === 'btnToggleBrake' ? 'map-tool-btn btn-brake-toggle active' : 'btn btn-warning btn-sm btn-brake-toggle active';
      } else {
        btn.textContent = 'BRAKE: OFF';
        btn.className = btn.id === 'btnToggleBrake' ? 'map-tool-btn btn-brake-toggle disabled' : 'btn btn-secondary btn-sm btn-brake-toggle disabled';
      }
    });
  }

  if (btnToggleBrake) btnToggleBrake.addEventListener('click', toggleBraking);
  if (btnTabToggleBrake) btnTabToggleBrake.addEventListener('click', toggleBraking);

  // Tab 4 Canvas Controls
  if (btnTabZoomIn) {
    btnTabZoomIn.addEventListener('click', () => {
      state.tabMapZoom = Math.min(300, state.tabMapZoom * 1.25);
      renderMapOnCanvas(tabSlamCanvas, state.tabMapZoom, state.tabMapPan);
    });
  }
  if (btnTabZoomOut) {
    btnTabZoomOut.addEventListener('click', () => {
      state.tabMapZoom = Math.max(25, state.tabMapZoom * 0.8);
      renderMapOnCanvas(tabSlamCanvas, state.tabMapZoom, state.tabMapPan);
    });
  }
  if (btnTabCenter) {
    btnTabCenter.addEventListener('click', () => {
      if (state.mapData && state.mapData.robot) {
        state.tabMapPan.x = -state.mapData.robot.x * state.tabMapZoom;
        state.tabMapPan.y = state.mapData.robot.y * state.tabMapZoom;
      } else {
        state.tabMapPan = { x: 0, y: 0 };
      }
      renderMapOnCanvas(tabSlamCanvas, state.tabMapZoom, state.tabMapPan);
    });
  }
  if (btnTabClear) {
    btnTabClear.addEventListener('click', async () => {
      if (!confirm('Clear all mapped obstacle points and movement trail?')) return;
      await fetch('/api/map/clear', { method: 'POST' });
      log('Cleared 2D room map.', 'warn');
      pollMapData();
    });
  }

  // -------------------------------------------------------------
  // SPEED SLIDERS
  // -------------------------------------------------------------
  driveSpeedRange.addEventListener('input', (e) => {
    state.driveSpeed = parseFloat(e.target.value);
    driveSpeedVal.textContent = `${state.driveSpeed.toFixed(1)} m/s`;
  });

  turnSpeedRange.addEventListener('input', (e) => {
    state.turnSpeed = parseInt(e.target.value);
    turnSpeedVal.textContent = `${state.turnSpeed} °/s`;
  });

  // -------------------------------------------------------------
  // MOTION CONTROL ENGINE
  // -------------------------------------------------------------
  async function sendDriveCommand(vx, vy, vz) {
    try {
      await fetch('/api/control/drive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vx, vy, vz }),
      });
    } catch (e) {
      console.error('Drive command error:', e);
    }
  }

  async function sendStopCommand() {
    try {
      await fetch('/api/control/stop', { method: 'POST' });
    } catch (e) {
      console.error('Stop command error:', e);
    }
  }

  btnEmergencyStop.addEventListener('click', () => {
    sendStopCommand();
    log('EMERGENCY STOP TRIGGERED', 'warn');
  });

  // D-PAD BUTTONS (CLICK & HOLD)
  const dpadButtons = document.querySelectorAll('.dpad-btn');
  dpadButtons.forEach((btn) => {
    const vxRaw = parseFloat(btn.dataset.vx || 0);
    const vyRaw = parseFloat(btn.dataset.vy || 0);
    const vzRaw = parseFloat(btn.dataset.vz || 0);

    const startAction = (e) => {
      e.preventDefault();
      btn.classList.add('active');

      if (btn.id === 'btnStop') {
        sendStopCommand();
        return;
      }

      const vx = vxRaw !== 0 ? Math.sign(vxRaw) * state.driveSpeed : 0;
      const vy = vyRaw !== 0 ? Math.sign(vyRaw) * state.driveSpeed : 0;
      const vz = vzRaw !== 0 ? Math.sign(vzRaw) * state.turnSpeed : 0;

      sendDriveCommand(vx, vy, vz);

      clearInterval(state.driveInterval);
      state.driveInterval = setInterval(() => {
        sendDriveCommand(vx, vy, vz);
      }, 100);
    };

    const stopAction = () => {
      btn.classList.remove('active');
      clearInterval(state.driveInterval);
      if (btn.id !== 'btnStop') {
        sendStopCommand();
      }
    };

    btn.addEventListener('mousedown', startAction);
    btn.addEventListener('mouseup', stopAction);
    btn.addEventListener('mouseleave', stopAction);
    btn.addEventListener('touchstart', startAction, { passive: false });
    btn.addEventListener('touchend', stopAction);
  });

  // -------------------------------------------------------------
  // KEYBOARD CONTROL ENGINE
  // -------------------------------------------------------------
  kbToggle.addEventListener('change', (e) => {
    state.keyboardEnabled = e.target.checked;
    log(`Keyboard control ${state.keyboardEnabled ? 'ENABLED' : 'DISABLED'}`);
  });

  function updateKeyboardDrive() {
    let vx = 0;
    let vy = 0;
    let vz = 0;

    if (state.activeKeys.has('w')) vx += state.driveSpeed;
    if (state.activeKeys.has('s')) vx -= state.driveSpeed;
    if (state.activeKeys.has('a')) vy -= state.driveSpeed;
    if (state.activeKeys.has('d')) vy += state.driveSpeed;
    if (state.activeKeys.has('q')) vz -= state.turnSpeed;
    if (state.activeKeys.has('e')) vz += state.turnSpeed;

    // Highlight D-pad buttons
    document.getElementById('btnFwd')?.classList.toggle('active', state.activeKeys.has('w'));
    document.getElementById('btnBack')?.classList.toggle('active', state.activeKeys.has('s'));
    document.getElementById('btnLeft')?.classList.toggle('active', state.activeKeys.has('a'));
    document.getElementById('btnRight')?.classList.toggle('active', state.activeKeys.has('d'));
    document.getElementById('btnRotLeft')?.classList.toggle('active', state.activeKeys.has('q'));
    document.getElementById('btnRotRight')?.classList.toggle('active', state.activeKeys.has('e'));

    if (vx === 0 && vy === 0 && vz === 0) {
      clearInterval(state.driveInterval);
      state.driveInterval = null;
      sendStopCommand();
    } else {
      sendDriveCommand(vx, vy, vz);
      if (!state.driveInterval) {
        state.driveInterval = setInterval(() => {
          sendDriveCommand(vx, vy, vz);
        }, 100);
      }
    }
  }

  window.addEventListener('keydown', (e) => {
    if (!state.keyboardEnabled) return;
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

    const key = e.key.toLowerCase();

    // Hotkeys
    if (key === 'c') {
      captureSnapshot();
      return;
    }
    if (key === 'r') {
      toggleRecording();
      return;
    }
    if (key === 'f') {
      toggleFullscreen();
      return;
    }
    // Spacebar toggles clamp open/close
    if (key === ' ' || e.key === ' ' || e.code === 'Space') {
      e.preventDefault();
      toggleClamp();
      return;
    }

    // X or Escape halts chassis
    if (key === 'x' || e.key === 'Escape') {
      e.preventDefault();
      state.activeKeys.clear();
      updateKeyboardDrive();
      sendStopCommand();
      return;
    }

    if (key === 'o') {
      controlGripper('open');
      return;
    }
    if (key === 'p') {
      controlGripper('close');
      return;
    }

    // Arrow keys control Robotic Arm
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      moveArm(0, 20);
      const b = document.getElementById('btnArmUp');
      if (b) { b.classList.add('active'); setTimeout(() => b.classList.remove('active'), 200); }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      moveArm(0, -20);
      const b = document.getElementById('btnArmDown');
      if (b) { b.classList.add('active'); setTimeout(() => b.classList.remove('active'), 200); }
      return;
    }
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      moveArm(-20, 0);
      const b = document.getElementById('btnArmBack');
      if (b) { b.classList.add('active'); setTimeout(() => b.classList.remove('active'), 200); }
      return;
    }
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      moveArm(20, 0);
      const b = document.getElementById('btnArmFwd');
      if (b) { b.classList.add('active'); setTimeout(() => b.classList.remove('active'), 200); }
      return;
    }
    if (e.key === 'Home' || key === 'h') {
      e.preventDefault();
      recenterArm();
      const b = document.getElementById('btnArmRecenter');
      if (b) { b.classList.add('active'); setTimeout(() => b.classList.remove('active'), 200); }
      return;
    }

    if (['w', 'a', 's', 'd', 'q', 'e'].includes(key)) {
      e.preventDefault();
      if (!state.activeKeys.has(key)) {
        state.activeKeys.add(key);
        updateKeyboardDrive();
      }
    }
  });

  window.addEventListener('keyup', (e) => {
    if (!state.keyboardEnabled) return;
    const key = e.key.toLowerCase();
    if (state.activeKeys.has(key)) {
      state.activeKeys.delete(key);
      updateKeyboardDrive();
    }
  });

  // -------------------------------------------------------------
  // ARM & GRIPPER CONTROLS
  // -------------------------------------------------------------
  async function moveArm(x, y) {
    log(`Moving arm: dx=${x}mm, dy=${y}mm`);
    try {
      await fetch('/api/control/arm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'move', x, y }),
      });
    } catch (e) {
      log(`Arm move failed: ${e}`, 'error');
    }
  }

  async function recenterArm() {
    log('Recentering arm to home pose...');
    try {
      await fetch('/api/control/arm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'recenter' }),
      });
      log('Arm recentered.', 'success');
    } catch (e) {
      log(`Arm recenter failed: ${e}`, 'error');
    }
  }

  async function controlGripper(action, power = 50) {
    if (action === 'open' || action === 'close') {
      state.gripperState = action;
    }
    log(`Clamp action: ${action.toUpperCase()}`);
    try {
      await fetch('/api/control/gripper', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, power }),
      });
    } catch (e) {
      log(`Clamp action failed: ${e}`, 'error');
    }
  }

  async function toggleClamp() {
    const nextAction = state.gripperState === 'open' ? 'close' : 'open';
    state.gripperState = nextAction;
    log(`Spacebar clamp toggle -> ${nextAction.toUpperCase()}`);
    await controlGripper(nextAction);

    // Visual button feedback
    const btn = nextAction === 'open' ? document.getElementById('btnGripperOpen') : document.getElementById('btnGripperClose');
    if (btn) {
      btn.classList.add('active');
      setTimeout(() => btn.classList.remove('active'), 250);
    }
  }

  document.getElementById('btnArmUp').addEventListener('click', () => moveArm(0, 20));
  document.getElementById('btnArmDown').addEventListener('click', () => moveArm(0, -20));
  document.getElementById('btnArmFwd').addEventListener('click', () => moveArm(20, 0));
  document.getElementById('btnArmBack').addEventListener('click', () => moveArm(-20, 0));
  document.getElementById('btnArmRecenter').addEventListener('click', recenterArm);

  document.getElementById('btnGripperOpen').addEventListener('click', () => controlGripper('open'));
  document.getElementById('btnGripperClose').addEventListener('click', () => controlGripper('close'));
  document.getElementById('btnGripperPause').addEventListener('click', () => controlGripper('pause'));

  // -------------------------------------------------------------
  // MEDIA CAPTURE & RECORDING
  // -------------------------------------------------------------
  async function captureSnapshot() {
    // Flash effect
    cameraFlash.classList.add('active');
    setTimeout(() => cameraFlash.classList.remove('active'), 250);

    log('Capturing snapshot...');
    try {
      const res = await fetch('/api/media/capture', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        log(`Snapshot saved: ${data.filename} (${(data.size_bytes / 1024).toFixed(1)} KB)`, 'success');
        loadGallery();
      } else {
        log('Snapshot capture failed', 'error');
      }
    } catch (e) {
      log(`Capture error: ${e}`, 'error');
    }
  }

  async function toggleRecording() {
    if (!state.isRecording) {
      log('Starting video recording...');
      try {
        const res = await fetch('/api/media/record/start', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          state.isRecording = true;
          log(`Recording started: ${data.filename}`, 'success');
        } else {
          log(`Recording start failed: ${data.message}`, 'error');
        }
      } catch (e) {
        log(`Recording error: ${e}`, 'error');
      }
    } else {
      log('Stopping video recording...');
      try {
        const res = await fetch('/api/media/record/stop', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          state.isRecording = false;
          log(`Recording saved: ${data.filename} (${data.duration_sec}s, ${(data.size_bytes / 1024 / 1024).toFixed(2)} MB)`, 'success');
          loadGallery();
        } else {
          log(`Recording stop failed: ${data.message}`, 'error');
        }
      } catch (e) {
        log(`Recording stop error: ${e}`, 'error');
      }
    }
  }

  btnCapture.addEventListener('click', captureSnapshot);
  btnRecord.addEventListener('click', toggleRecording);

  function toggleFullscreen() {
    const elem = document.getElementById('videoContainer');
    if (!document.fullscreenElement) {
      elem.requestFullscreen?.() || elem.webkitRequestFullscreen?.();
    } else {
      document.exitFullscreen?.() || document.webkitExitFullscreen?.();
    }
  }

  btnFullscreen.addEventListener('click', toggleFullscreen);

  // Restart Camera Button
  const btnRestartCamera = document.getElementById('btnRestartCamera');
  if (btnRestartCamera) {
    btnRestartCamera.addEventListener('click', async () => {
      btnRestartCamera.disabled = true;
      const span = btnRestartCamera.querySelector('span');
      if (span) span.textContent = 'RESETTING...';
      log('Requesting camera stream reset...', 'warn');
      try {
        const res = await fetch('/api/camera/restart', { method: 'POST' });
        const d = await res.json();
        if (d.success) {
          log('Camera stream restarted successfully!', 'success');
          const videoFeedEl = document.getElementById('cameraStream');
          if (videoFeedEl) {
            videoFeedEl.src = `/video_feed?t=${Date.now()}`;
          }
        } else {
          log('Camera reset rejected by rover', 'error');
        }
      } catch (e) {
        log(`Camera reset error: ${e}`, 'error');
      }
      setTimeout(() => {
        btnRestartCamera.disabled = false;
        if (span) span.textContent = 'RESET CAM';
      }, 1500);
    });
  }

  // -------------------------------------------------------------
  // WI-FI PAIRING & AUTO-CONNECT
  // -------------------------------------------------------------
  btnUsbConnect?.addEventListener('click', async () => {
    wifiStatusAlert.textContent = 'Connecting via USB (RNDIS)...';
    wifiStatusAlert.style.borderColor = 'var(--accent-cyan)';
    log('Attempting USB (RNDIS) direct connection to 192.168.42.2...', 'warn');

    try {
      const res = await fetch('/api/wifi/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip: '192.168.42.2', conn_type: 'rndis' }),
      });
      const data = await res.json();
      if (data.success) {
        wifiStatusAlert.textContent = 'Connected via USB (RNDIS)!';
        wifiStatusAlert.style.borderColor = 'var(--accent-green)';
        log('Rover successfully connected via USB (RNDIS)!', 'success');
      } else {
        wifiStatusAlert.textContent = `USB Connection: ${data.message}`;
        wifiStatusAlert.style.borderColor = 'var(--accent-red)';
        log(`USB connection attempt: ${data.message}`, 'error');
      }
    } catch (e) {
      wifiStatusAlert.textContent = `USB Error: ${e}`;
    }
  });

  btnAutoConnect.addEventListener('click', async () => {
    wifiStatusAlert.textContent = 'Scanning network for RoboMaster EP rover...';
    wifiStatusAlert.style.borderColor = 'var(--accent-gold)';
    log('Scanning network for RoboMaster EP on Samsung Wi-Fi...', 'warn');

    try {
      const res = await fetch('/api/wifi/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conn_type: 'sta' }),
      });
      const data = await res.json();
      if (data.success) {
        wifiStatusAlert.textContent = `Connected! Rover IP: ${data.rover_ip}`;
        wifiStatusAlert.style.borderColor = 'var(--accent-green)';
        log(`Rover successfully connected at IP: ${data.rover_ip}`, 'success');
      } else {
        wifiStatusAlert.textContent = `Rover not detected: ${data.message}`;
        wifiStatusAlert.style.borderColor = 'var(--accent-red)';
        log(`Connection attempt: ${data.message}`, 'warn');
      }
    } catch (e) {
      wifiStatusAlert.textContent = `Connection error: ${e}`;
      wifiStatusAlert.style.borderColor = 'var(--accent-red)';
    }
  });

  btnManualConnect.addEventListener('click', async () => {
    const ip = manualIpInput.value.trim();
    if (!ip) {
      alert('Please enter a valid IP address (e.g. 10.37.75.x or 192.168.2.1)');
      return;
    }
    wifiStatusAlert.textContent = `Attempting connection to ${ip}...`;
    log(`Connecting to manually specified IP: ${ip}...`);

    try {
      const res = await fetch('/api/wifi/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip, conn_type: 'sta' }),
      });
      const data = await res.json();
      if (data.success) {
        wifiStatusAlert.textContent = `Connected to ${data.rover_ip}!`;
        wifiStatusAlert.style.borderColor = 'var(--accent-green)';
        log(`Connected to rover at ${data.rover_ip}`, 'success');
      } else {
        wifiStatusAlert.textContent = `Connection failed: ${data.message}`;
        wifiStatusAlert.style.borderColor = 'var(--accent-red)';
        log(`Failed connecting to ${ip}: ${data.message}`, 'error');
      }
    } catch (e) {
      wifiStatusAlert.textContent = `Error: ${e}`;
    }
  });

  btnDisconnect.addEventListener('click', async () => {
    await fetch('/api/wifi/disconnect', { method: 'POST' });
    wifiStatusAlert.textContent = 'Rover disconnected.';
    wifiStatusAlert.style.borderColor = 'var(--border-color)';
    log('Rover disconnected by user.', 'warn');
  });

  // -------------------------------------------------------------
  // BOTTOM TABS
  // -------------------------------------------------------------
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      tabBtns.forEach((b) => b.classList.remove('active'));
      tabPanes.forEach((p) => p.classList.remove('active'));

      btn.classList.add('active');
      const targetTab = document.getElementById(btn.dataset.tab);
      if (targetTab) targetTab.classList.add('active');

      if (btn.dataset.tab === 'tabMedia') {
        loadGallery();
      } else if (btn.dataset.tab === 'tabMap') {
        setTimeout(() => {
          renderMapOnCanvas(tabSlamCanvas, state.tabMapZoom, state.tabMapPan);
        }, 50);
      }
    });
  });

  // -------------------------------------------------------------
  // MEDIA GALLERY
  // -------------------------------------------------------------
  filterBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      filterBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      state.currentFilter = btn.dataset.filter;
      renderGallery();
    });
  });

  btnRefreshGallery.addEventListener('click', loadGallery);

  let cachedFiles = [];

  async function loadGallery() {
    try {
      const res = await fetch('/api/media/list');
      const data = await res.json();
      cachedFiles = data.files || [];

      const totalMb = cachedFiles.reduce((acc, f) => acc + f.size_mb, 0).toFixed(1);
      galleryStats.textContent = `${cachedFiles.length} files (${totalMb} MB)`;
      mediaCountBadge.textContent = cachedFiles.length;

      renderGallery();
    } catch (e) {
      console.error('Gallery load error:', e);
    }
  }

  function renderGallery() {
    mediaGrid.innerHTML = '';

    const filtered = cachedFiles.filter((f) => {
      if (state.currentFilter === 'all') return true;
      return f.type === state.currentFilter;
    });

    if (filtered.length === 0) {
      mediaGrid.innerHTML = '<div class="empty-state">No media found matching this filter.</div>';
      return;
    }

    filtered.forEach((file) => {
      const card = document.createElement('div');
      card.className = 'media-card';

      const thumb = document.createElement('div');
      thumb.className = 'media-thumb';

      if (file.type === 'video') {
        thumb.innerHTML = `
          <video src="${file.url}#t=0.5" preload="metadata"></video>
          <span class="media-badge video">VIDEO</span>
        `;
      } else {
        thumb.innerHTML = `
          <img src="${file.url}" alt="${file.name}" loading="lazy">
          <span class="media-badge">PHOTO</span>
        `;
      }

      thumb.addEventListener('click', () => openModal(file));

      const body = document.createElement('div');
      body.className = 'media-card-body';
      body.innerHTML = `
        <span class="media-name" title="${file.name}">${file.name}</span>
        <div class="media-info">
          <span>${file.size_mb} MB</span>
          <span>${file.modified}</span>
        </div>
        <div class="media-actions">
          <a href="${file.url}" download="${file.name}" class="btn btn-secondary btn-sm">Save</a>
          <button class="btn btn-danger btn-sm btn-delete" data-file="${file.name}">Delete</button>
        </div>
      `;

      body.querySelector('.btn-delete').addEventListener('click', (e) => {
        e.stopPropagation();
        deleteMediaFile(file.name);
      });

      card.appendChild(thumb);
      card.appendChild(body);
      mediaGrid.appendChild(card);
    });
  }

  // -------------------------------------------------------------
  // MODAL PREVIEW
  // -------------------------------------------------------------
  function openModal(file) {
    state.activeModalFile = file;
    modalTitle.textContent = file.name;
    modalDownloadBtn.href = file.url;
    modalDownloadBtn.download = file.name;

    if (file.type === 'video') {
      modalBody.innerHTML = `<video src="${file.url}" controls autoplay style="width: 100%; max-height: 55vh;"></video>`;
    } else {
      modalBody.innerHTML = `<img src="${file.url}" alt="${file.name}" style="max-width: 100%; max-height: 55vh; object-fit: contain;">`;
    }

    mediaModal.style.display = 'flex';
  }

  function closeModal() {
    mediaModal.style.display = 'none';
    modalBody.innerHTML = '';
    state.activeModalFile = null;
  }

  modalClose.addEventListener('click', closeModal);
  mediaModal.addEventListener('click', (e) => {
    if (e.target === mediaModal) closeModal();
  });

  modalDeleteBtn.addEventListener('click', () => {
    if (state.activeModalFile) {
      deleteMediaFile(state.activeModalFile.name);
      closeModal();
    }
  });

  async function deleteMediaFile(filename) {
    if (!confirm(`Delete ${filename}?`)) return;
    try {
      const res = await fetch(`/api/media/delete/${filename}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        log(`Deleted file: ${filename}`, 'warn');
        loadGallery();
      } else {
        alert(`Delete failed: ${data.message}`);
      }
    } catch (e) {
      alert(`Delete error: ${e}`);
    }
  }

  // Initial gallery load
  loadGallery();
});

