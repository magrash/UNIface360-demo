// Initialize particles.js on any page that has a #particles-js container.
// This keeps the config in one place and avoids duplicating it in templates.

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.particlesJS) return;
    var container = document.getElementById("particles-js");
    if (!container) return;

    particlesJS("particles-js", {
      particles: {
        number: { value: 600,density: { enable: true, value_area: 80 } },
        color: { value: ["#22d3ee", "#a855f7", "#38bdf8"] },
        shape: { type: "circle" },
        opacity: { value: 0.4, random: true },
        size: { value: 2.5, random: true },
        line_linked: { enable: false },
        move: {
          enable: true,
          speed: 5.9,
          direction: "none",
          random: true,
          straight: false,
          out_mode: "out"
        }
      },
      interactivity: {
        detect_on: "canvas",
        events: {
          onhover: { enable: false },
          onclick: { enable: false },
          resize: true
        }
      },
      retina_detect: true
    });
  });
})();












