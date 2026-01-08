// Shared demo logic for UNIface360 detection pages
// - Camera setup per page
// - Frame capture + backend calls
// - Futuristic alert popups + beep
// - Dynamic camera selection

(function () {
  "use strict";

  const qs = (sel) => document.querySelector(sel);
  
  // Global camera list cache
  let availableCameras = {};
  let modelCameras = {};  // Cameras configured for specific models
  
  // ---------------- Camera List Management ----------------
  
  async function loadCameraList() {
    try {
      const response = await fetch('/api/rtsp/cameras');
      availableCameras = await response.json();
      return availableCameras;
    } catch (err) {
      console.error('Failed to load camera list:', err);
      return {};
    }
  }
  
  // Load cameras configured for a specific model (unauthorized, restricted, ppe)
  async function loadModelCameras(modelType) {
    try {
      const response = await fetch(`/api/model-cameras/${modelType}`);
      const data = await response.json();
      if (data.ok) {
        modelCameras[modelType] = data.cameras || {};
        return modelCameras[modelType];
      }
      return {};
    } catch (err) {
      console.error(`Failed to load ${modelType} cameras:`, err);
      return {};
    }
  }
  
  // Populate select with model-specific cameras (only enabled ones)
  // showRestricted: null = show all, true = only restricted, false = only non-restricted
  // showSmokingZone: null = show all, true = only smoking zones, false = only non-smoking zones
  function populateModelCameraSelect(selectEl, modelType, showRestricted = null, showSmokingZone = null) {
    if (!selectEl) return;
    
    selectEl.innerHTML = '';
    const cameras = modelCameras[modelType] || {};
    let cameraEntries = Object.entries(cameras);
    
    // Filter by enabled
    cameraEntries = cameraEntries.filter(([id, cam]) => cam.enabled);
    
    // For restricted model, optionally filter by is_restricted flag
    if (modelType === 'restricted' && showRestricted !== null) {
      cameraEntries = cameraEntries.filter(([id, cam]) => cam.is_restricted === showRestricted);
    }
    
    // For smoking model, optionally filter by is_smoking_zone flag
    if (modelType === 'smoking' && showSmokingZone !== null) {
      cameraEntries = cameraEntries.filter(([id, cam]) => cam.is_smoking_zone === showSmokingZone);
    }
    
    if (cameraEntries.length === 0) {
      const opt = document.createElement('option');
      opt.value = '-1';
      opt.textContent = 'No cameras configured - Add in Manage page';
      opt.disabled = true;
      selectEl.appendChild(opt);
      return;
    }
    
    cameraEntries.sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
    
    let isFirst = true;
    for (const [id, cam] of cameraEntries) {
      const opt = document.createElement('option');
      opt.value = id;
      opt.textContent = cam.name || `Camera ${id}`;
      if (modelType === 'restricted') {
        opt.textContent += cam.is_restricted ? ' 🔴' : ' 🟢';
      }
      if (modelType === 'smoking') {
        opt.textContent += cam.is_smoking_zone ? ' 🔥' : ' 🟢';
      }
      if (isFirst) {
        opt.selected = true;
        isFirst = false;
      }
      selectEl.appendChild(opt);
    }
  }
  
  function populateCameraSelect(selectEl, defaultValue = 0) {
    if (!selectEl) return;
    
    selectEl.innerHTML = '';
    const cameras = Object.entries(availableCameras);
    
    if (cameras.length === 0) {
      const opt = document.createElement('option');
      opt.value = '0';
      opt.textContent = 'No cameras configured';
      selectEl.appendChild(opt);
      return;
    }
    
    cameras.sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
    
    for (const [id, cam] of cameras) {
      const opt = document.createElement('option');
      opt.value = id;
      opt.textContent = `${cam.name} (Camera ${id})`;
      if (!cam.enabled) {
        opt.textContent += ' [Disabled]';
        opt.style.color = '#888';
      }
      if (parseInt(id) === defaultValue) {
        opt.selected = true;
      }
      selectEl.appendChild(opt);
    }
  }
  
  function getSelectedCamera(selectId) {
    const select = qs(selectId);
    return select ? parseInt(select.value) : 0;
  }

  // ---------------- Alerts ----------------

  function showAlert(opts) {
    const {
      type = "info",
      title = "Detection",
      message = "An event occurred.",
      severity = "warning",
      source = "frontend",
    } = opts || {};

    const layer = qs("#alert-layer");
    if (!layer) return;

    const box = document.createElement("div");
    box.className = "uf-alert";
    if (severity === "critical") box.classList.add("uf-alert--critical");
    else if (severity === "warning") box.classList.add("uf-alert--warning");

    const chip = document.createElement("div");
    chip.className = "uf-alert-type-chip";
    if (type === "restricted" || type === "unauthorized") {
      chip.classList.add("uf-alert-type-chip--restricted");
    }
    chip.textContent = type.toUpperCase();

    const content = document.createElement("div");
    content.className = "uf-alert-content";
    const t = document.createElement("p");
    t.className = "uf-alert-title";
    t.textContent = title;
    const m = document.createElement("p");
    m.className = "uf-alert-message";
    m.textContent = message;
    const meta = document.createElement("div");
    meta.className = "uf-alert-meta";
    const src = document.createElement("span");
    src.textContent = source === "frontend" ? "Source: demo UI" : "Source: backend";
    meta.appendChild(src);
    content.appendChild(t);
    content.appendChild(m);
    content.appendChild(meta);

    const close = document.createElement("button");
    close.type = "button";
    close.className = "uf-alert-close";
    close.setAttribute("aria-label", "Dismiss alert");
    close.textContent = "×";
    close.addEventListener("click", () => dismissAlert(box));

    box.appendChild(chip);
    box.appendChild(content);
    box.appendChild(close);

    layer.appendChild(box);
    playBeep(severity);
    setTimeout(() => dismissAlert(box), 4200);
  }

  function dismissAlert(el) {
    if (!el || el.classList.contains("uf-alert--leaving")) return;
    el.classList.add("uf-alert--leaving");
    el.addEventListener(
      "animationend",
      () => {
        if (el.parentNode) el.parentNode.removeChild(el);
      },
      { once: true }
    );
  }

  function playBeep(severity) {
    try {
      const Ctx =
        window.AudioContext || window.webkitAudioContext || window.mozAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = severity === "critical" ? 1150 : 880;
      gain.gain.value = 0.08;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.18);
    } catch (e) {
      // sound is optional
    }
  }

  // ---------------- Camera helper (cv2-based backend streaming) ----------------

  async function attachCamera(videoEls, statusEls, cameraIndices = null) {
    statusEls.forEach((el) => el && (el.textContent = "Connecting to camera…"));

    try {
      // Use cv2-based backend streaming via MJPEG endpoints
      if (cameraIndices && cameraIndices.length > 0) {
        for (let i = 0; i < videoEls.length; i++) {
          const camIndex = cameraIndices[i] !== undefined ? cameraIndices[i] : (cameraIndices[0] || 0);
          
          const videoEl = videoEls[i];
          if (!videoEl) {
            console.warn(`Video element at index ${i} is null or undefined`);
            if (statusEls[i]) {
              statusEls[i].textContent = `Camera ${camIndex} element not found`;
            }
            continue;
          }
          
          const streamUrl = `/video_feed/${camIndex}`;
          console.log(`Setting up camera ${camIndex} for element ${videoEl.id || i}`);
          
          // For MJPEG streams, we need to use img elements
          // Convert video to img if needed
          if (videoEl.tagName === 'VIDEO') {
            // Check if element is still in DOM
            if (!videoEl.parentNode) {
              console.warn(`Video element ${videoEl.id || i} has no parent node, skipping`);
              if (statusEls[i]) {
                statusEls[i].textContent = `Camera ${camIndex} element not in DOM`;
              }
              continue;
            }
            
            // Create img element to replace video for MJPEG
            const img = document.createElement('img');
            img.id = videoEl.id;
            img.className = videoEl.className;
            img.style.cssText = videoEl.style.cssText;
            img.src = streamUrl;
            img.style.width = '100%';
            img.style.height = 'auto';
            img.style.objectFit = 'cover';
            
            // Replace video with img safely
            try {
              videoEl.parentNode.replaceChild(img, videoEl);
              videoEls[i] = img; // Update reference in original array
              console.log(`Successfully replaced video with img for camera ${camIndex}`);
            } catch (e) {
              console.error(`Failed to replace video element for camera ${camIndex}:`, e);
              if (statusEls[i]) {
                statusEls[i].textContent = `Camera ${camIndex} setup failed`;
              }
              continue;
            }
            
            img.onload = () => {
              if (statusEls[i]) {
                statusEls[i].textContent = `Live (Camera ${camIndex})`;
              }
              console.log(`Camera ${camIndex} stream loaded successfully`);
            };
            
            img.onerror = () => {
              if (statusEls[i]) {
                statusEls[i].textContent = `Camera ${camIndex} connection failed`;
              }
              console.error(`Camera ${camIndex} stream failed to load`);
            };
          } else if (videoEl.tagName === 'IMG') {
            videoEl.src = streamUrl;
            videoEl.onload = () => {
              if (statusEls[i]) {
                statusEls[i].textContent = `Live (Camera ${camIndex})`;
              }
              console.log(`Camera ${camIndex} stream loaded successfully`);
            };
            videoEl.onerror = () => {
              if (statusEls[i]) {
                statusEls[i].textContent = `Camera ${camIndex} connection failed`;
              }
              console.error(`Camera ${camIndex} stream failed to load`);
            };
          } else {
            console.warn(`Unexpected element type for camera ${camIndex}: ${videoEl.tagName}`);
            if (statusEls[i]) {
              statusEls[i].textContent = `Camera ${camIndex} unsupported element type`;
            }
          }
          
          // Set initial status
          if (statusEls[i]) {
            setTimeout(() => {
              if (statusEls[i].textContent === "Connecting to camera…") {
                statusEls[i].textContent = `Live (Camera ${camIndex})`;
              }
            }, 1000);
          }
        }
      } else {
        // Default: use camera 0 for all
        const defaultIndex = 0;
        videoEls.forEach((v, idx) => {
          if (v && v.parentNode) {
            const streamUrl = `/video_feed/${defaultIndex}`;
            if (v.tagName === 'VIDEO') {
              const img = document.createElement('img');
              img.id = v.id;
              img.className = v.className;
              img.style.cssText = v.style.cssText;
              img.src = streamUrl;
              img.style.width = '100%';
              img.style.height = 'auto';
              img.style.objectFit = 'cover';
              try {
                v.parentNode.replaceChild(img, v);
              } catch (e) {
                console.error(`Failed to replace video element: ${e}`);
              }
            } else if (v.tagName === 'IMG') {
              v.src = streamUrl;
            }
          }
        });
        statusEls.forEach(
          (el, idx) =>
            el &&
            (el.textContent =
              idx === 0 ? "Live (Camera 0)" : "Live (Camera 0, shared)")
        );
      }
    } catch (err) {
      console.error("Camera error", err);
      statusEls.forEach(
        (el) =>
          el &&
          (el.textContent =
            "Could not access camera. Check if cameras are connected.")
      );
    }
  }

  function captureFrame(video) {
    if (!video) return null;
    
    // Handle both video and img elements (MJPEG streams)
    let width, height;
    if (video.tagName === 'VIDEO') {
      if (!video.videoWidth) return null;
      width = video.videoWidth;
      height = video.videoHeight;
    } else if (video.tagName === 'IMG') {
      // For MJPEG streams, be more lenient - try to capture even if not fully loaded
      // Use naturalWidth/Height if available, otherwise use displayed dimensions
      if (video.naturalWidth && video.naturalWidth > 0) {
        width = video.naturalWidth;
        height = video.naturalHeight;
      } else if (video.width && video.width > 0) {
        width = video.width;
        height = video.height;
      } else {
        // Try with default dimensions if image exists
        width = 640;
        height = 480;
      }
    } else {
      return null;
    }
    
    try {
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL("image/jpeg", 0.8);
    } catch (e) {
      console.error("Failed to capture frame:", e);
      return null;
    }
  }

  async function postJson(url, payload) {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return resp.json();
  }

  // ---------------- Page initialisers ----------------

  function initSmoking() {
    const v1 = qs("#smoke-cam-normal");
    const v2 = qs("#smoke-cam-restricted");
    const s1 = qs("#smoke-normal-status");
    const s2 = qs("#smoke-restricted-status");
    const startBtn = qs("#smoke-start-cam");
    const simBtn = qs("#smoke-simulate");
    const lastResult = qs("#smoke-last-result");
    const normalSelect = qs("#camera-select-normal");
    const restrictedSelect = qs("#camera-select-restricted");
    
    let checkInterval = null;
    let normalCameraIndex = 0;     // Camera for normal zone (display only)
    let restrictedCameraIndex = 1; // Camera for restricted/smoking zone (detection)
    
    // Throttling for emergency sound - only play once per cooldown period
    let lastEmergencySoundTime = 0;
    const EMERGENCY_SOUND_COOLDOWN = 30000; // 30 seconds in milliseconds
    let emergencyAudio = null;
    
    // Throttling for email alerts - only send once per cooldown period
    let lastEmailAlertTime = 0;
    const EMAIL_ALERT_COOLDOWN = 60000; // 1 minute in milliseconds
    
    // Hide the simulate button since we're using real detection
    if (simBtn) {
      simBtn.style.display = "none";
    }
    
    // Load cameras configured for Smoking model
    async function initCameraSelectors() {
      await loadModelCameras('smoking');
      // Normal cameras - NOT marked as smoking zone
      populateModelCameraSelect(normalSelect, 'smoking', null, false);
      // Smoking zone cameras - marked as smoking zone
      populateModelCameraSelect(restrictedSelect, 'smoking', null, true);
      
      normalCameraIndex = getSelectedCamera("#camera-select-normal");
      restrictedCameraIndex = getSelectedCamera("#camera-select-restricted");
      
      // Show message if no cameras configured
      if (normalCameraIndex < 0) {
        if (s1) s1.textContent = "⚠️ No normal cameras. Go to Manage → Smoke/Fire and add cameras.";
      }
      if (restrictedCameraIndex < 0) {
        if (s2) s2.textContent = "⚠️ No smoking zone cameras. Go to Manage → Smoke/Fire and mark a camera as Smoking Zone.";
      }
    }
    
    // Handle normal camera selection change
    if (normalSelect) {
      normalSelect.addEventListener('change', () => {
        normalCameraIndex = getSelectedCamera("#camera-select-normal");
        console.log(`[SMOKING] Normal camera changed to: ${normalCameraIndex}`);
        if (v1) {
          attachCamera([v1], [s1], [normalCameraIndex]);
        }
      });
    }
    
    // Handle smoking zone camera selection change
    if (restrictedSelect) {
      restrictedSelect.addEventListener('change', () => {
        restrictedCameraIndex = getSelectedCamera("#camera-select-restricted");
        console.log(`[SMOKING] Smoking zone camera changed to: ${restrictedCameraIndex}`);
        if (v2) {
          attachCamera([v2], [s2], [restrictedCameraIndex]);
        }
      });
    }
    
    // Initialize camera selectors
    initCameraSelectors();
    
    // Function to play emergency sound with throttling
    function playEmergencySound() {
      const now = Date.now();
      const timeSinceLastPlay = now - lastEmergencySoundTime;
      
      // Only play if enough time has passed since last play
      if (timeSinceLastPlay >= EMERGENCY_SOUND_COOLDOWN) {
        try {
          // Create or reuse audio element
          if (!emergencyAudio) {
            emergencyAudio = new Audio("/static/emergency.mp3");
            emergencyAudio.volume = 0.7; // Set volume to 70%
          }
          
          // Reset and play
          emergencyAudio.currentTime = 0;
          emergencyAudio.play().catch(err => {
            console.warn("Could not play emergency sound:", err);
          });
          
          // Update last play time
          lastEmergencySoundTime = now;
        } catch (e) {
          console.warn("Emergency sound playback failed:", e);
        }
      }
    }
    
    // Function to send email alert with throttling
    async function sendEmailAlert(detectionType) {
      const now = Date.now();
      const timeSinceLastEmail = now - lastEmailAlertTime;
      
      // Only send if enough time has passed since last email
      if (timeSinceLastEmail >= EMAIL_ALERT_COOLDOWN) {
        try {
          const res = await postJson("/api/demo/smoking/send-alert-email", {
            detection_type: detectionType,
            camera_index: restrictedCameraIndex
          });
          
          if (res.ok) {
            console.log("Smoking/fire email alert sent successfully");
            lastEmailAlertTime = now;
          } else {
            console.warn("Smoking email alert failed or was throttled:", res.message);
          }
        } catch (err) {
          console.error("Failed to send smoking email alert:", err);
        }
      } else {
        console.log(`Smoking email alert throttled. Last sent ${timeSinceLastEmail}ms ago. Need ${EMAIL_ALERT_COOLDOWN}ms cooldown.`);
      }
    }
    
    // Function to perform the smoke/fire check
    async function performCheck() {
      try {
        console.log("[SMOKE] Performing check...");
        // Send camera index directly to backend - backend will capture frame
        const res = await postJson("/api/demo/smoking/check", { camera_index: restrictedCameraIndex });
        console.log("[SMOKE] Response:", res);
        
        if (res.error === "camera_not_available") {
          console.warn("[SMOKE] Camera not available");
          if (s2) {
            s2.textContent = "Camera not ready...";
          }
          return;
        }
        
        if (res.error === "model_not_loaded") {
          console.error("[SMOKE] Model not loaded");
          if (s2) {
            s2.textContent = "Smoke model not loaded. Check server logs.";
          }
          return;
        }
        
        // Check for detections
        const smokeDetected = res.smoke_detected;
        const fireDetected = res.fire_detected;
        
        if (fireDetected && smokeDetected) {
          console.log("[SMOKE] CRITICAL - Both smoke and fire detected!");
          showAlert({
            type: "smoking",
            title: "🔥 CRITICAL: Smoke AND Fire Detected!",
            message: "Smoke and fire detected in monitoring zone. Evacuate immediately and contact emergency services!",
            severity: "critical",
            source: "backend",
          });
          playEmergencySound();
          sendEmailAlert("both");
          if (lastResult) {
            lastResult.textContent = `🔥 CRITICAL - Smoke & Fire detected!`;
            lastResult.style.color = "#ff4444";
          }
          if (s2) {
            s2.textContent = "🔥 CRITICAL: SMOKE + FIRE DETECTED!";
          }
        } else if (fireDetected) {
          const conf = res.fire_confidence ? ` (${(res.fire_confidence * 100).toFixed(0)}%)` : "";
          console.log(`[SMOKE] FIRE detected${conf}!`);
          showAlert({
            type: "smoking",
            title: "🔥 Fire Detected!",
            message: "Fire detected in monitoring zone. Take immediate action!",
            severity: "critical",
            source: "backend",
          });
          playEmergencySound();
          sendEmailAlert("fire");
          if (lastResult) {
            lastResult.textContent = `🔥 FIRE detected${conf}!`;
            lastResult.style.color = "#ff4444";
          }
          if (s2) {
            s2.textContent = "🔥 FIRE DETECTED!";
          }
        } else if (smokeDetected) {
          const conf = res.smoke_confidence ? ` (${(res.smoke_confidence * 100).toFixed(0)}%)` : "";
          console.log(`[SMOKE] SMOKE detected${conf}!`);
          showAlert({
            type: "smoking",
            title: "🚨 Smoke Detected!",
            message: "Smoke detected in non-smoking zone. HSE and security are notified.",
            severity: "critical",
            source: "backend",
          });
          playEmergencySound();
          sendEmailAlert("smoke");
          if (lastResult) {
            lastResult.textContent = `🚨 SMOKE detected${conf}!`;
            lastResult.style.color = "#ffaa00";
          }
          if (s2) {
            s2.textContent = "🚨 SMOKE DETECTED!";
          }
        } else {
          // No detection - all clear
          console.log("[SMOKE] No smoke/fire detected - all clear");
          if (lastResult) {
            lastResult.textContent = "✓ All clear - No smoke or fire detected";
            lastResult.style.color = "#44ff44";
          }
          if (s2) {
            s2.textContent = "✓ Monitoring - No hazards detected";
          }
        }
      } catch (err) {
        console.error("[SMOKE] Check error:", err);
        if (s2) {
          s2.textContent = "Error checking. See console.";
        }
      }
    }

    startBtn &&
      startBtn.addEventListener("click", () => {
        // Use selected cameras
        normalCameraIndex = getSelectedCamera("#camera-select-normal");
        restrictedCameraIndex = getSelectedCamera("#camera-select-restricted");
        attachCamera([v1, v2], [s1, s2], [normalCameraIndex, restrictedCameraIndex]);
        
        // Start automatic checking after a short delay to allow camera to initialize
        if (checkInterval) {
          clearInterval(checkInterval);
        }
        
        // Wait 3 seconds for camera to initialize, then start checking every 2 seconds
        setTimeout(() => {
          checkInterval = setInterval(performCheck, 2000); // Check every 2 seconds
          if (s2) {
            s2.textContent = "Camera active - Auto-detecting smoke/fire...";
          }
          // Perform first check immediately
          performCheck();
        }, 3000);
      });
  }

  function initUnauthorized() {
    const v = qs("#unauth-cam");
    const status = qs("#unauth-status");
    const startBtn = qs("#unauth-start-cam");
    const checkBtn = qs("#unauth-check");
    const lastResult = qs("#unauth-last-result");
    const cameraSelect = qs("#camera-select");
    const refreshBtn = qs("#refresh-cameras-btn");
    
    let checkInterval = null;
    let currentCameraIndex = 0; // Will be updated from selector
    
    // Throttling for emergency sound - only play once per minute
    let lastEmergencySoundTime = 0;
    const EMERGENCY_SOUND_COOLDOWN = 30000; // 30 seconds in milliseconds
    let emergencyAudio = null;
    
    // Throttling for email alerts - only send once per cooldown period
    let lastEmailAlertTime = 0;
    const EMAIL_ALERT_COOLDOWN = 60000; // 1 minute in milliseconds (matches sound cooldown)

    // Hide the check button since we're doing automatic detection
    if (checkBtn) {
      checkBtn.style.display = "none";
    }
    
    // Load cameras configured for Unauthorized model
    async function initCameraSelector() {
      await loadModelCameras('unauthorized');
      populateModelCameraSelect(cameraSelect, 'unauthorized');
      currentCameraIndex = getSelectedCamera("#camera-select");
      
      // Show message if no cameras configured
      if (currentCameraIndex < 0) {
        if (status) status.textContent = "⚠️ No cameras configured. Go to Manage → Unauthorized to add cameras.";
      }
    }
    
    // Handle camera selection change
    if (cameraSelect) {
      cameraSelect.addEventListener('change', () => {
        currentCameraIndex = getSelectedCamera("#camera-select");
        console.log(`[UNAUTHORIZED] Camera changed to: ${currentCameraIndex}`);
        // Restart camera stream with new selection
        if (v) {
          attachCamera([v], [status], [currentCameraIndex]);
        }
      });
    }
    
    // Handle refresh button
    if (refreshBtn) {
      refreshBtn.addEventListener('click', async () => {
        refreshBtn.style.animation = 'spin 1s linear';
        await initCameraSelector();
        setTimeout(() => refreshBtn.style.animation = '', 1000);
      });
    }
    
    // Initialize camera selector
    initCameraSelector();
    
    // Function to play emergency sound with throttling
    function playEmergencySound() {
      const now = Date.now();
      const timeSinceLastPlay = now - lastEmergencySoundTime;
      
      // Only play if enough time has passed since last play
      if (timeSinceLastPlay >= EMERGENCY_SOUND_COOLDOWN) {
        try {
          // Create or reuse audio element
          if (!emergencyAudio) {
            emergencyAudio = new Audio("/static/emergency.mp3");
            emergencyAudio.volume = 0.7; // Set volume to 70%
          }
          
          // Reset and play
          emergencyAudio.currentTime = 0;
          emergencyAudio.play().catch(err => {
            console.warn("Could not play emergency sound:", err);
          });
          
          // Update last play time
          lastEmergencySoundTime = now;
        } catch (e) {
          console.warn("Emergency sound playback failed:", e);
        }
      }
    }
    
    // Function to send email alert with throttling
    async function sendEmailAlert(personInfo = "Unknown person") {
      const now = Date.now();
      const timeSinceLastEmail = now - lastEmailAlertTime;
      
      // Only send if enough time has passed since last email
      if (timeSinceLastEmail >= EMAIL_ALERT_COOLDOWN) {
        try {
          const res = await postJson("/api/demo/unauthorized/send-alert-email", {
            person_info: personInfo,
            camera_index: currentCameraIndex
          });
          
          if (res.ok) {
            console.log("Email alert sent successfully");
            lastEmailAlertTime = now;
          } else {
            console.warn("Email alert failed or was throttled:", res.message);
          }
        } catch (err) {
          console.error("Failed to send email alert:", err);
        }
      } else {
        console.log(`Email alert throttled. Last sent ${timeSinceLastEmail}ms ago. Need ${EMAIL_ALERT_COOLDOWN}ms cooldown.`);
      }
    }

    // Function to perform the unauthorized check
    async function performCheck() {
      try {
        // Send camera index directly to backend - backend will capture frame
        const res = await postJson("/api/demo/unauthorized/check", { camera_index: currentCameraIndex });
        
        if (res.error === "camera_not_available") {
          // Don't show alert for camera not available during automatic checks
          // Just update status silently
          if (status) {
            status.textContent = "Camera not ready...";
          }
          return;
        }
        
        // Only show alert when there's actually an unauthorized face detected
        // Don't alert when no face is detected (reason === "no_face")
        if (res.unauthorized && res.reason !== "no_face") {
          // This means a face was detected but it's not in the authorized list
          showAlert({
            type: "unauthorized",
            title: "Unauthorized / unknown person detected",
            message: "Face is not in the authorized list. Please verify and respond according to procedure.",
            severity: "critical",
            source: "backend",
          });
          // Play emergency sound (throttled to once per cooldown period)
          playEmergencySound();
          // Send email alert (throttled to once per cooldown period)
          sendEmailAlert("Unknown person");
          if (lastResult)
            lastResult.textContent = "Last result: UNAUTHORIZED (unknown person).";
        } else if (!res.unauthorized) {
          // Authorized person detected
          const name = res.person_name || "Known person";
          if (lastResult)
            lastResult.textContent = "Last result: authorized as " + name + ".";
        } else if (res.reason === "no_face") {
          // No face detected - silently update status, don't show alert
          if (lastResult)
            lastResult.textContent = "Last result: No face detected.";
        }
      } catch (err) {
        console.error(err);
        // Don't spam alerts for network errors during automatic checks
        // Only log to console
      }
    }

    startBtn &&
      startBtn.addEventListener("click", () => {
        // Use selected camera
        currentCameraIndex = getSelectedCamera("#camera-select");
        attachCamera([v], [status], [currentCameraIndex]);
        
        // Start automatic checking after a short delay to allow camera to initialize
        // Clear any existing interval first
        if (checkInterval) {
          clearInterval(checkInterval);
        }
        
        // Wait 3 seconds for camera to initialize, then start checking every 2 seconds
        setTimeout(() => {
          checkInterval = setInterval(performCheck, 2000); // Check every 2 seconds
          if (status) {
            status.textContent = "Camera active - Auto-detecting unauthorized persons...";
          }
          // Perform first check immediately
          performCheck();
        }, 3000);
      });
  }

  function initRestricted() {
    const v1 = qs("#rest-cam-restricted");  // First div - restricted
    const v2 = qs("#rest-cam-normal");       // Second div - normal
    const s1 = qs("#rest-restricted-status");
    const s2 = qs("#rest-normal-status");
    const startBtn = qs("#rest-start-cam");
    const checkBtn = qs("#rest-check");
    const restrictedSelect = qs("#camera-select-restricted");
    const normalSelect = qs("#camera-select-normal");
    
    let checkInterval = null;
    let restrictedCameraIndex = 0; // Camera for restricted zone (detection)
    let normalCameraIndex = 1;     // Camera for normal zone (display only)
    
    // Throttling for emergency sound - only play once per cooldown period
    let lastEmergencySoundTime = 0;
    const EMERGENCY_SOUND_COOLDOWN = 30000; // 30 seconds in milliseconds
    let emergencyAudio = null;
    
    // Throttling for email alerts - only send once per cooldown period
    let lastEmailAlertTime = 0;
    const EMAIL_ALERT_COOLDOWN = 60000; // 1 minute in milliseconds
    
    // Hide the check button since we're doing automatic detection
    if (checkBtn) {
      checkBtn.style.display = "none";
    }
    
    // Load cameras configured for Restricted model
    async function initCameraSelectors() {
      await loadModelCameras('restricted');
      // Restricted camera dropdown - only cameras marked as restricted
      populateModelCameraSelect(restrictedSelect, 'restricted', true);
      // Normal camera dropdown - only cameras NOT marked as restricted
      populateModelCameraSelect(normalSelect, 'restricted', false);
      
      restrictedCameraIndex = getSelectedCamera("#camera-select-restricted");
      normalCameraIndex = getSelectedCamera("#camera-select-normal");
      
      // Show message if no cameras configured
      if (restrictedCameraIndex < 0) {
        if (s1) s1.textContent = "⚠️ No restricted cameras. Go to Manage → Restricted and mark a camera as Restricted.";
      }
      if (normalCameraIndex < 0) {
        if (s2) s2.textContent = "⚠️ No normal cameras. Go to Manage → Restricted and add cameras (unmark Restricted).";
      }
    }
    
    // Handle restricted camera selection change
    if (restrictedSelect) {
      restrictedSelect.addEventListener('change', () => {
        restrictedCameraIndex = getSelectedCamera("#camera-select-restricted");
        console.log(`[RESTRICTED] Restricted camera changed to: ${restrictedCameraIndex}`);
        if (v1) {
          attachCamera([v1], [s1], [restrictedCameraIndex]);
        }
      });
    }
    
    // Handle normal camera selection change
    if (normalSelect) {
      normalSelect.addEventListener('change', () => {
        normalCameraIndex = getSelectedCamera("#camera-select-normal");
        console.log(`[RESTRICTED] Normal camera changed to: ${normalCameraIndex}`);
        if (v2) {
          attachCamera([v2], [s2], [normalCameraIndex]);
        }
      });
    }
    
    // Initialize camera selectors
    initCameraSelectors();
    
    // Function to play emergency sound with throttling
    function playEmergencySound() {
      const now = Date.now();
      const timeSinceLastPlay = now - lastEmergencySoundTime;
      
      // Only play if enough time has passed since last play
      if (timeSinceLastPlay >= EMERGENCY_SOUND_COOLDOWN) {
        try {
          // Create or reuse audio element
          if (!emergencyAudio) {
            emergencyAudio = new Audio("/static/emergency.mp3");
            emergencyAudio.volume = 0.7; // Set volume to 70%
          }
          
          // Reset and play
          emergencyAudio.currentTime = 0;
          emergencyAudio.play().catch(err => {
            console.warn("Could not play emergency sound:", err);
          });
          
          // Update last play time
          lastEmergencySoundTime = now;
        } catch (e) {
          console.warn("Emergency sound playback failed:", e);
        }
      }
    }
    
    // Function to send email alert with throttling
    async function sendEmailAlert() {
      const now = Date.now();
      const timeSinceLastEmail = now - lastEmailAlertTime;
      
      // Only send if enough time has passed since last email
      if (timeSinceLastEmail >= EMAIL_ALERT_COOLDOWN) {
        try {
          // Include camera_index so backend can capture frame snapshot
          const res = await postJson("/api/demo/restricted/send-alert-email", {
            camera_index: restrictedCameraIndex
          });
          
          if (res.ok) {
            console.log("Restricted area email alert sent successfully with snapshot");
            lastEmailAlertTime = now;
          } else {
            // Check if it's throttled or an actual error
            if (res.reason === "throttled") {
              console.log(`Email alert throttled by backend: ${res.message}`);
              // Update frontend throttling time to match backend
              lastEmailAlertTime = now - (EMAIL_ALERT_COOLDOWN - 1000); // Set to almost expired
            } else {
              console.error("Email alert failed:", res.message, res.reason);
            }
          }
        } catch (err) {
          console.error("Failed to send email alert:", err);
          // If it's a 429 error, it means backend throttled
          if (err.status === 429 || (err.response && err.response.status === 429)) {
            console.log("Email alert throttled by backend (429)");
            lastEmailAlertTime = now - (EMAIL_ALERT_COOLDOWN - 1000);
          }
        }
      } else {
        console.log(`Email alert throttled (frontend). Last sent ${timeSinceLastEmail}ms ago. Need ${EMAIL_ALERT_COOLDOWN}ms cooldown.`);
      }
    }
    
    // Function to perform the restricted area check
    async function performCheck() {
      try {
        // Send camera index directly to backend - backend will capture frame
        const res = await postJson("/api/demo/restricted/check", { camera_index: restrictedCameraIndex });
        
        if (res.error === "camera_not_available") {
          // Don't show alert for camera not available during automatic checks
          // Just update status silently
          if (s1) {
            s1.textContent = "Camera not ready...";
          }
          return;
        }
        
        // Only show alert when intruder is detected
        if (res.intruder) {
          showAlert({
            type: "restricted",
            title: "Restricted area breach detected",
            message: "A person has been detected inside the restricted safety zone. Initiate response plan.",
            severity: "critical",
            source: "backend",
          });
          // Play emergency sound (throttled to once per cooldown period)
          playEmergencySound();
          // Send email alert (throttled to once per cooldown period)
          sendEmailAlert();
        }
        // Don't show alert when zone is clear - just silently continue monitoring
      } catch (err) {
        console.error(err);
        // Don't spam alerts for network errors during automatic checks
        // Only log to console
      }
    }

    startBtn &&
      startBtn.addEventListener("click", () => {
        // Use selected cameras
        restrictedCameraIndex = getSelectedCamera("#camera-select-restricted");
        normalCameraIndex = getSelectedCamera("#camera-select-normal");
        attachCamera([v1, v2], [s1, s2], [restrictedCameraIndex, normalCameraIndex]);
        
        // Start automatic checking after a short delay to allow camera to initialize
        // Clear any existing interval first
        if (checkInterval) {
          clearInterval(checkInterval);
        }
        
        // Wait 3 seconds for camera to initialize, then start checking every 2 seconds
        setTimeout(() => {
          checkInterval = setInterval(performCheck, 2000); // Check every 2 seconds
          if (s1) {
            s1.textContent = "Camera active - Auto-detecting restricted area breaches...";
          }
          // Perform first check immediately
          performCheck();
        }, 3000);
      });
  }

  function initPPE() {
    const v = qs("#ppe-cam");
    const status = qs("#ppe-status");
    const startBtn = qs("#ppe-start-cam");
    const toggleBtn = qs("#ppe-toggle");
    const checkBtn = qs("#ppe-check");
    const lastResult = qs("#ppe-last-result");
    const cameraSelect = qs("#camera-select");
    const refreshBtn = qs("#refresh-cameras-btn");
    
    let checkInterval = null;
    let currentCameraIndex = 0; // Will be updated from selector
    
    // Throttling for emergency sound - only play once per cooldown period
    let lastEmergencySoundTime = 0;
    const EMERGENCY_SOUND_COOLDOWN = 30000; // 30 seconds in milliseconds
    let emergencyAudio = null;
    
    // Throttling for email alerts - only send once per cooldown period
    let lastEmailAlertTime = 0;
    const EMAIL_ALERT_COOLDOWN = 60000; // 1 minute in milliseconds
    
    // Hide the toggle button since we're using real YOLO detection
    if (toggleBtn) {
      toggleBtn.style.display = "none";
    }
    
    // Hide the check button since we're doing automatic detection
    if (checkBtn) {
      checkBtn.style.display = "none";
    }
    
    // Load cameras configured for PPE model
    async function initCameraSelector() {
      await loadModelCameras('ppe');
      populateModelCameraSelect(cameraSelect, 'ppe');
      currentCameraIndex = getSelectedCamera("#camera-select");
      
      // Show message if no cameras configured
      if (currentCameraIndex < 0) {
        if (status) status.textContent = "⚠️ No cameras configured. Go to Manage → PPE to add cameras.";
      }
    }
    
    // Handle camera selection change
    if (cameraSelect) {
      cameraSelect.addEventListener('change', () => {
        currentCameraIndex = getSelectedCamera("#camera-select");
        console.log(`[PPE] Camera changed to: ${currentCameraIndex}`);
        // Restart camera stream with new selection
        if (v) {
          attachCamera([v], [status], [currentCameraIndex]);
        }
      });
    }
    
    // Handle refresh button
    if (refreshBtn) {
      refreshBtn.addEventListener('click', async () => {
        refreshBtn.style.animation = 'spin 1s linear';
        await initCameraSelector();
        setTimeout(() => refreshBtn.style.animation = '', 1000);
      });
    }
    
    // Initialize camera selector
    initCameraSelector();
    
    // Function to play emergency sound with throttling
    function playEmergencySound() {
      const now = Date.now();
      const timeSinceLastPlay = now - lastEmergencySoundTime;
      
      // Only play if enough time has passed since last play
      if (timeSinceLastPlay >= EMERGENCY_SOUND_COOLDOWN) {
        try {
          // Create or reuse audio element
          if (!emergencyAudio) {
            emergencyAudio = new Audio("/static/emergency.mp3");
            emergencyAudio.volume = 0.7; // Set volume to 70%
          }
          
          // Reset and play
          emergencyAudio.currentTime = 0;
          emergencyAudio.play().catch(err => {
            console.warn("Could not play emergency sound:", err);
          });
          
          // Update last play time
          lastEmergencySoundTime = now;
        } catch (e) {
          console.warn("Emergency sound playback failed:", e);
        }
      }
    }
    
    // Function to send email alert with throttling
    async function sendEmailAlert() {
      const now = Date.now();
      const timeSinceLastEmail = now - lastEmailAlertTime;
      
      // Only send if enough time has passed since last email
      if (timeSinceLastEmail >= EMAIL_ALERT_COOLDOWN) {
        try {
          const res = await postJson("/api/demo/ppe/send-alert-email", {
            camera_index: currentCameraIndex
          });
          
          if (res.ok) {
            console.log("PPE violation email alert sent successfully");
            lastEmailAlertTime = now;
          } else {
            console.warn("PPE email alert failed or was throttled:", res.message);
          }
        } catch (err) {
          console.error("Failed to send PPE email alert:", err);
        }
      } else {
        console.log(`PPE email alert throttled. Last sent ${timeSinceLastEmail}ms ago. Need ${EMAIL_ALERT_COOLDOWN}ms cooldown.`);
      }
    }
    
    // Function to perform the PPE check
    async function performCheck() {
      try {
        console.log("[PPE] Performing check...");
        // Send camera index directly to backend - backend will capture frame
        const res = await postJson("/api/demo/ppe/check", { camera_index: currentCameraIndex });
        console.log("[PPE] Response:", res);
        
        if (res.error === "camera_not_available") {
          // Don't show alert for camera not available during automatic checks
          console.warn("[PPE] Camera not available");
          if (status) {
            status.textContent = "Camera not ready...";
          }
          return;
        }
        
        if (res.error === "model_not_loaded") {
          console.error("[PPE] Model not loaded");
          if (status) {
            status.textContent = "PPE model not loaded. Check server logs.";
          }
          return;
        }
        
        // Check for violation (no hardhat detected)
        if (res.violation) {
          console.log("[PPE] VIOLATION - No hardhat detected!");
          showAlert({
            type: "ppe",
            title: "PPE Violation – Hardhat Not Detected",
            message: "Worker detected without a hardhat in a mandatory PPE zone. Please intervene immediately.",
            severity: "critical",
            source: "backend",
          });
          // Play emergency sound (throttled)
          playEmergencySound();
          // Send email alert (throttled)
          sendEmailAlert();
          if (lastResult) {
            lastResult.textContent = "⚠️ VIOLATION - No hardhat detected!";
            lastResult.style.color = "#ff4444";
          }
          if (status) {
            status.textContent = "⚠️ PPE VIOLATION DETECTED!";
          }
        } else {
          // Hardhat detected - all good
          const conf = res.confidence ? ` (${(res.confidence * 100).toFixed(0)}%)` : "";
          console.log(`[PPE] OK - Hardhat detected${conf}`);
          if (lastResult) {
            lastResult.textContent = `✓ OK - Hardhat detected${conf}`;
            lastResult.style.color = "#44ff44";
          }
          if (status) {
            status.textContent = "✓ PPE Compliant - Hardhat detected";
          }
        }
      } catch (err) {
        console.error("[PPE] Check error:", err);
        if (status) {
          status.textContent = "Error checking PPE. See console.";
        }
      }
    }

    startBtn &&
      startBtn.addEventListener("click", () => {
        // Use selected camera for PPE detection
        currentCameraIndex = getSelectedCamera("#camera-select");
        attachCamera([v], [status], [currentCameraIndex]);
        
        // Start automatic checking after a short delay to allow camera to initialize
        if (checkInterval) {
          clearInterval(checkInterval);
        }
        
        // Wait 3 seconds for camera to initialize, then start checking every 2 seconds
        setTimeout(() => {
          checkInterval = setInterval(performCheck, 2000); // Check every 2 seconds
          if (status) {
            status.textContent = "Camera active - Auto-detecting PPE compliance...";
          }
          // Perform first check immediately
          performCheck();
        }, 3000);
      });
  }

  // ---------------- Init dispatcher ----------------

  document.addEventListener("DOMContentLoaded", () => {
    const body = document.body;
    if (!body) return;
    const page = body.getAttribute("data-page");

    if (page === "smoking") initSmoking();
    else if (page === "unauthorized") initUnauthorized();
    else if (page === "restricted") initRestricted();
    else if (page === "ppe") initPPE();
  });
})();


