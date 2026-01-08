// UNIface360 Realtime Safety Demo frontend logic
// ------------------------------------------------------------
// Responsibilities:
// - Initialize camera feeds using getUserMedia()
// - Maintain an SSE connection to /events
// - Provide helpers to trigger four detection types
//   (smoking, unauthorized person, restricted area, PPE)
// - Render futuristic popups with glow & animation
// - Play a short beep tone per alert

(function () {
  "use strict";

  const qs = (sel) => document.querySelector(sel);

  const els = {
    exploreSection: qs("#explore-demo"),
    btnExploreScroll: qs("#btn-explore-scroll"),
    btnResetAlerts: qs("#btn-reset-alerts"),

    statusEvacuation: qs("#status-evacuation"),
    statusUnauthorized: qs("#status-unauthorized"),
    statusRestricted: qs("#status-restricted"),
    statusPPE: qs("#status-ppe"),

    camNormal: qs("#cam-normal"),
    camRestricted: qs("#cam-restricted"),
    camNormalStatus: qs("#cam-normal-status"),
    camRestrictedStatus: qs("#cam-restricted-status"),

    sseStatus: qs("#sse-status"),
    alertLayer: qs("#alert-layer"),

    btnEvacuationLocal: qs("#btn-evacuation-local"),
    btnEvacuationBackend: qs("#btn-evacuation-backend"),
    btnUnauthLocal: qs("#btn-unauth-local"),
    btnUnauthBackend: qs("#btn-unauth-backend"),
    btnRestrictedLocal: qs("#btn-restricted-local"),
    btnRestrictedBackend: qs("#btn-restricted-backend"),
    btnPpeLocal: qs("#btn-ppe-local"),
    btnPpeBackend: qs("#btn-ppe-backend"),
  };

  // ----------------------------------------------------------
  // Camera setup
  // ----------------------------------------------------------

  async function initCameras() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCamStatus(
        "normal",
        "Camera API not supported by this browser. Try a recent Chrome or Edge."
      );
      setCamStatus(
        "restricted",
        "Camera API not supported by this browser. Try a recent Chrome or Edge."
      );
      return;
    }

    try {
      setCamStatus("normal", "Requesting camera access…");

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });

      if (els.camNormal) {
        els.camNormal.srcObject = stream;
      }
      if (els.camRestricted) {
        els.camRestricted.srcObject = stream;
      }

      setCamStatus("normal", "Live");
      setCamStatus("restricted", "Live (visual overlay only)");
    } catch (err) {
      console.error("Failed to initialize camera:", err);
      const message =
        err && err.name === "NotAllowedError"
          ? "Camera permission was denied. Allow access and refresh to view live feeds."
          : "Could not access the camera. Check device permissions and availability.";
      setCamStatus("normal", message);
      setCamStatus("restricted", message);
    }
  }

  function setCamStatus(which, text) {
    if (which === "normal" && els.camNormalStatus) {
      els.camNormalStatus.textContent = text;
    }
    if (which === "restricted" && els.camRestrictedStatus) {
      els.camRestrictedStatus.textContent = text;
    }
  }

  // ----------------------------------------------------------
  // SSE connection
  // ----------------------------------------------------------

  let eventSource = null;

  function initSSE() {
    if (!window.EventSource) {
      setSseStatus("SSE not supported in this browser", "error");
      return;
    }

    setSseStatus("SSE: connecting…", "pending");
    eventSource = new EventSource("/events");

    eventSource.onopen = () => {
      setSseStatus("SSE: connected", "ok");
    };

    eventSource.onerror = () => {
      // EventSource will attempt to reconnect automatically.
      setSseStatus("SSE: reconnecting…", "error");
    };

    eventSource.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data);
        handleDetectionEvent(payload);
      } catch (err) {
        console.error("Failed to parse SSE message", err);
      }
    };
  }

  function setSseStatus(text, state) {
    if (!els.sseStatus) return;

    els.sseStatus.textContent = text;
    els.sseStatus.classList.remove("uf-nav-status--ok", "uf-nav-status--error");

    if (state === "ok") {
      els.sseStatus.classList.add("uf-nav-status--ok");
    } else if (state === "error") {
      els.sseStatus.classList.add("uf-nav-status--error");
    }
  }

  // ----------------------------------------------------------
  // Detection handling
  // ----------------------------------------------------------

  function handleDetectionEvent(evt) {
    if (!evt || !evt.type) return;

    const type = evt.type;
    const source = evt.source || "backend";

    switch (type) {
      case "evacuation":
        triggerEvacuationAlert(source, evt);
        break;
      case "unauthorized":
        triggerUnauthorizedAlert(source, evt);
        break;
      case "restricted":
        triggerRestrictedAlert(source, evt);
        break;
      case "ppe":
        triggerPPEAlert(source, evt);
        break;
      default:
        showAlert({
          type,
          title: evt.demo || "Detection event",
          message: evt.message || "A new detection event has been received.",
          severity: evt.level || "warning",
          source,
          timestamp: evt.timestamp,
        });
    }
  }

  function setDetectionStatus(which, text, mode) {
    let el = null;
    switch (which) {
      case "evacuation":
        el = els.statusEvacuation;
        break;
      case "unauthorized":
        el = els.statusUnauthorized;
        break;
      case "restricted":
        el = els.statusRestricted;
        break;
      case "ppe":
        el = els.statusPPE;
        break;
      default:
        break;
    }

    if (!el) return;

    el.textContent = text;
    el.classList.remove("uf-status-badge--active", "uf-status-badge--backend");
    if (mode === "frontend") {
      el.classList.add("uf-status-badge--active");
    } else if (mode === "backend") {
      el.classList.add("uf-status-badge--backend");
    }

    // Reset back to idle after a short delay
    window.setTimeout(() => {
      el.textContent = "Idle";
      el.classList.remove("uf-status-badge--active", "uf-status-badge--backend");
    }, 3500);
  }

  function triggerEvacuationAlert(source, evt) {
    setDetectionStatus(
      "evacuation",
      source === "frontend" ? "Simulated locally" : "Event from backend",
      source
    );

    showAlert({
      type: "evacuation",
      title: "Evacuation System",
      message:
        (evt && evt.message) ||
        "Person detected for evacuation tracking.",
      severity: "info",
      source,
      timestamp: evt && evt.timestamp,
    });
  }

  function triggerUnauthorizedAlert(source, evt) {
    setDetectionStatus(
      "unauthorized",
      source === "frontend" ? "Unknown face (simulated)" : "Unknown face (backend)",
      source
    );

    showAlert({
      type: "unauthorized",
      title: "Unauthorized Person",
      message:
        (evt && evt.message) ||
        'Face recognition result: "unknown" in a controlled zone. Security check required.',
      severity: "critical",
      source,
      timestamp: evt && evt.timestamp,
    });
  }

  function triggerRestrictedAlert(source, evt) {
    setDetectionStatus(
      "restricted",
      source === "frontend" ? "Restricted zone breach (simulated)" : "Restricted zone breach",
      source
    );

    showAlert({
      type: "restricted",
      title: "Restricted Area Breach",
      message:
        (evt && evt.message) ||
        "Movement detected inside a restricted safety zone. Activate response plan.",
      severity: "critical",
      source,
      timestamp: evt && evt.timestamp,
    });
  }

  function triggerPPEAlert(source, evt) {
    setDetectionStatus(
      "ppe",
      source === "frontend" ? "PPE violation (simulated)" : "PPE violation (backend)",
      source
    );

    showAlert({
      type: "ppe",
      title: "PPE Violation – Missing Hardhat",
      message:
        (evt && evt.message) ||
        "Hardhat not detected on worker in a mandatory PPE zone. Please intervene.",
      severity: "warning",
      source,
      timestamp: evt && evt.timestamp,
    });
  }

  // ----------------------------------------------------------
  // Alert popups + audio
  // ----------------------------------------------------------

  function showAlert(options) {
    const {
      type = "info",
      title = "Detection",
      message = "A new detection event has occurred.",
      severity = "warning",
      source = "backend",
      timestamp,
    } = options || {};

    if (!els.alertLayer) return;

    const wrapper = document.createElement("div");
    wrapper.className = "uf-alert";
    if (severity === "critical") {
      wrapper.classList.add("uf-alert--critical");
    } else if (severity === "warning") {
      wrapper.classList.add("uf-alert--warning");
    }

    const chip = document.createElement("div");
    chip.className = "uf-alert-type-chip";
    if (type === "restricted" || type === "unauthorized") {
      chip.classList.add("uf-alert-type-chip--restricted");
    }
    chip.textContent = type.toUpperCase();

    const content = document.createElement("div");
    content.className = "uf-alert-content";

    const titleEl = document.createElement("p");
    titleEl.className = "uf-alert-title";
    titleEl.textContent = title;

    const msgEl = document.createElement("p");
    msgEl.className = "uf-alert-message";
    msgEl.textContent = message;

    const meta = document.createElement("div");
    meta.className = "uf-alert-meta";
    const srcSpan = document.createElement("span");
    srcSpan.textContent = source === "frontend" ? "Source: demo UI" : "Source: backend";
    meta.appendChild(srcSpan);

    if (timestamp) {
      const tsSpan = document.createElement("span");
      tsSpan.textContent = new Date(timestamp).toLocaleTimeString();
      meta.appendChild(tsSpan);
    }

    content.appendChild(titleEl);
    content.appendChild(msgEl);
    content.appendChild(meta);

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "uf-alert-close";
    closeBtn.setAttribute("aria-label", "Dismiss alert");
    closeBtn.textContent = "×";

    closeBtn.addEventListener("click", () => dismissAlert(wrapper));

    wrapper.appendChild(chip);
    wrapper.appendChild(content);
    wrapper.appendChild(closeBtn);

    els.alertLayer.appendChild(wrapper);

    playBeep(severity);

    // Auto-dismiss after a few seconds
    window.setTimeout(() => dismissAlert(wrapper), 4300);
  }

  function dismissAlert(el) {
    if (!el || el.classList.contains("uf-alert--leaving")) return;
    el.classList.add("uf-alert--leaving");
    el.addEventListener(
      "animationend",
      () => {
        if (el.parentNode) {
          el.parentNode.removeChild(el);
        }
      },
      { once: true }
    );
  }

  function clearAllAlerts() {
    if (!els.alertLayer) return;
    const alerts = Array.from(els.alertLayer.querySelectorAll(".uf-alert"));
    alerts.forEach((a) => dismissAlert(a));
  }

  function playBeep(severity) {
    try {
      const AudioContext =
        window.AudioContext || window.webkitAudioContext || window.mozAudioContext;
      if (!AudioContext) return;

      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sine";
      osc.frequency.value = severity === "critical" ? 1120 : 880;

      gain.gain.value = 0.08;

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + 0.18);
    } catch (err) {
      // Non-fatal: sound is optional
      console.warn("Unable to play beep", err);
    }
  }

  // ----------------------------------------------------------
  // Button wiring
  // ----------------------------------------------------------

  function wireButtons() {
    if (els.btnExploreScroll && els.exploreSection) {
      els.btnExploreScroll.addEventListener("click", () => {
        els.exploreSection.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }

    if (els.btnResetAlerts) {
      els.btnResetAlerts.addEventListener("click", clearAllAlerts);
    }

    if (els.btnEvacuationLocal) {
      els.btnEvacuationLocal.addEventListener("click", () => {
        triggerEvacuationAlert("frontend");
      });
    }
    if (els.btnEvacuationBackend) {
      els.btnEvacuationBackend.addEventListener("click", () => {
        backendTrigger("/trigger/evacuation", "evacuation");
      });
    }

    if (els.btnUnauthLocal) {
      els.btnUnauthLocal.addEventListener("click", () => {
        triggerUnauthorizedAlert("frontend");
      });
    }
    if (els.btnUnauthBackend) {
      els.btnUnauthBackend.addEventListener("click", () => {
        backendTrigger("/trigger/unauthorized", "unauthorized");
      });
    }

    if (els.btnRestrictedLocal) {
      els.btnRestrictedLocal.addEventListener("click", () => {
        triggerRestrictedAlert("frontend");
      });
    }
    if (els.btnRestrictedBackend) {
      els.btnRestrictedBackend.addEventListener("click", () => {
        backendTrigger("/trigger/restricted", "restricted");
      });
    }

    if (els.btnPpeLocal) {
      els.btnPpeLocal.addEventListener("click", () => {
        triggerPPEAlert("frontend");
      });
    }
    if (els.btnPpeBackend) {
      els.btnPpeBackend.addEventListener("click", () => {
        backendTrigger("/trigger/ppe", "ppe");
      });
    }
  }

  async function backendTrigger(url, type) {
    setDetectionStatus(type, "Triggering via backend…", "backend");
    try {
      const resp = await fetch(url, { method: "POST" });
      if (!resp.ok) {
        throw new Error("HTTP " + resp.status);
      }
      // SSE will deliver the resulting event.
    } catch (err) {
      console.error("Backend trigger failed", err);
      setDetectionStatus(type, "Backend trigger failed", "backend");
      showAlert({
        type,
        title: "Backend trigger failed",
        message: "Could not reach the Flask trigger endpoint. Is demo.py running?",
        severity: "warning",
        source: "frontend",
      });
    }
  }

  // ----------------------------------------------------------
  // Init
  // ----------------------------------------------------------

  document.addEventListener("DOMContentLoaded", () => {
    wireButtons();
    initCameras();
    initSSE();
  });
})();


