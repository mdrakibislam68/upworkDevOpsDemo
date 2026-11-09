/**
 * app.js — Minimal JavaScript for the deployment demo page.
 *
 * Purpose:
 *   Provides a simple runtime status check: attempts a fetch to the Nginx
 *   health endpoint (/healthz) and updates the status badge accordingly.
 *   This is cosmetic only — it does NOT imply any external service is healthy.
 */

(function () {
  "use strict";

  const badge    = document.getElementById("status-badge");
  const dot      = badge && badge.querySelector(".status-dot");
  const label    = badge && badge.querySelector(".status-text");

  /**
   * updateBadge — set the status badge appearance.
   * @param {"ok"|"warn"|"error"} state
   * @param {string} text
   */
  function updateBadge(state, text) {
    if (!badge) return;

    const colours = {
      ok:    { dot: "#2ea043", glow: "rgba(46,160,67,0.6)"  },
      warn:  { dot: "#d29922", glow: "rgba(210,153,34,0.6)" },
      error: { dot: "#f85149", glow: "rgba(248,81,73,0.6)"  },
    };

    const c = colours[state] || colours.ok;

    if (dot) {
      dot.style.background  = c.dot;
      dot.style.boxShadow   = "0 0 0 0 " + c.glow;
    }
    if (label) label.textContent = text;
  }

  /**
   * checkHealth — fetch /healthz and reflect the result in the badge.
   * Falls back gracefully if fetch is unavailable (very old browsers).
   */
  function checkHealth() {
    if (typeof fetch === "undefined") return; // bail on old browsers

    fetch("/healthz", { method: "GET", cache: "no-store" })
      .then(function (res) {
        if (res.ok) {
          updateBadge("ok", "Application Running");
        } else {
          updateBadge("warn", "Proxy Reachable — App Status Unknown");
        }
      })
      .catch(function () {
        updateBadge("error", "Unable to reach health endpoint");
      });
  }

  // Run once on load, then every 30 seconds.
  checkHealth();
  setInterval(checkHealth, 30000);
})();

