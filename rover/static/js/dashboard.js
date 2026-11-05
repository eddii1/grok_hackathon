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
    currentFilter: 'all',
    activeModalFile: null,
  };

  // --- DOM ELEMENTS ---
  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');
  const connStatusPill = document.getElementById('connStatusPill');
  const roverIpEl = document.getElementById('roverIp');
  const batteryBar = document.getElementById('batteryBar');
  const batteryText = document.getElementById('batteryText');
  const recPill = document.getElementById('recPill');
  const recTimer = document.getElementById('recTimer');
  const hudTimestamp = document.getElementById('hudTimestamp');
  const hudSpeeds = document.getElementById('hudSpeeds');
  const hudRecordingTag = document.getElementById('hudRecordingTag');
  const cameraFlash = document.getElementById('cameraFlash');

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
    if (key === ' ') {
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
    log(`Gripper action: ${action.toUpperCase()}`);
    try {
      await fetch('/api/control/gripper', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, power }),
      });
    } catch (e) {
      log(`Gripper action failed: ${e}`, 'error');
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

