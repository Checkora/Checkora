/**
 * customisation.js
 * Board theme + piece-set selection for Checkora.
 *
 * Responsibilities:
 *  1. Load saved preferences on page start (backend for auth users, localStorage for anon)
 *  2. Apply the active theme / piece set to the DOM
 *  3. Save changes back to backend or localStorage
 *
 * Requires:
 *  - A <div id="customisation-panel"> in board.html  (or injected by this script)
 *  - themes.css loaded on the page
 *  - CSRF token available via getCookie('csrftoken') (Django default)
 */

(() => {
  "use strict";

  // ── Configuration ────────────────────────────────────────────────────────

  const BOARD_THEMES = ["classic", "green", "blue", "midnight"];
  const PIECE_SETS   = ["classic", "neo", "minimal"];

  // Base URL for piece images.  chess.com CDN pattern:
  //   https://images.chesscomfiles.com/chess-themes/pieces/{set}/150/{piece}.png
  // where {piece} is e.g. "wK", "bQ" etc.
  const PIECE_CDN = "https://images.chesscomfiles.com/chess-themes/pieces";

  // Map piece-set name → CDN folder name (adjust if CDN names differ)
  const PIECE_SET_CDN_MAP = {
    classic: "neo",      // chess.com "neo" = classic look; adjust as needed
    neo:     "neo",
    minimal: "bases",    // adjust to whichever CDN folder you prefer
  };

  // Selector for all piece <img> elements on the board
  const PIECE_IMG_SELECTOR = ".piece img, img.piece, [data-piece]";

  // Whether the user is logged in (set by Django template, see board.html snippet)
  const IS_AUTHENTICATED = window.CHECKORA_USER_AUTHENTICATED === true;

  // ── Utilities ────────────────────────────────────────────────────────────

  function getCookie(name) {
    const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : null;
  }

  // ── Preference storage ───────────────────────────────────────────────────

  function loadPrefsFromLocalStorage() {
    return {
      board_theme: localStorage.getItem("board_theme") || "classic",
      piece_set:   localStorage.getItem("piece_set")   || "classic",
    };
  }

  function savePrefsToLocalStorage(prefs) {
    localStorage.setItem("board_theme", prefs.board_theme);
    localStorage.setItem("piece_set",   prefs.piece_set);
  }

  async function loadPrefsFromBackend() {
    const res = await fetch("/api/preferences/", {
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error("Failed to fetch preferences");
    return res.json();
  }

  async function savePrefsToBackend(prefs) {
    await fetch("/api/preferences/", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify(prefs),
    });
  }

  async function loadPrefs() {
    if (IS_AUTHENTICATED) {
      try {
        return await loadPrefsFromBackend();
      } catch {
        // Fall back to localStorage if backend unavailable
        return loadPrefsFromLocalStorage();
      }
    }
    return loadPrefsFromLocalStorage();
  }

  async function savePrefs(prefs) {
    if (IS_AUTHENTICATED) {
      await savePrefsToBackend(prefs);
    }
    // Always keep localStorage in sync (fast restoration on next load)
    savePrefsToLocalStorage(prefs);
  }

  // ── DOM application ──────────────────────────────────────────────────────

  function applyBoardTheme(theme) {
    document.documentElement.setAttribute("data-board-theme", theme);
  }

  /**
   * Rebuild all piece <img> src attributes for the given piece set.
   *
   * Each img is expected to have a data-piece attribute like "wK", "bQ" etc.
   * If not present, the function attempts to parse the current src basename.
   */
  function applyPieceSet(pieceSet) {
    const cdnFolder = PIECE_SET_CDN_MAP[pieceSet] || pieceSet;
    document.querySelectorAll(PIECE_IMG_SELECTOR).forEach(img => {
      const pieceCode = img.dataset.piece || extractPieceCode(img.src);
      if (pieceCode) {
        img.src = `${PIECE_CDN}/${cdnFolder}/150/${pieceCode}.png`;
      }
    });
  }

  function extractPieceCode(src) {
    // e.g. ".../wK.png" → "wK"
    const match = src.match(/([bw][KQRBNP])\.(?:png|svg)$/i);
    return match ? match[1] : null;
  }

  // ── Panel injection ──────────────────────────────────────────────────────

  function buildPanel(currentPrefs) {
    let panel = document.getElementById("customisation-panel");
    if (!panel) {
      panel = document.createElement("div");
      panel.id = "customisation-panel";
      document.body.appendChild(panel);
    }

    panel.innerHTML = `
      <h3>🎨 Board Style</h3>

      <label for="board-theme-select">Board Theme</label>
      <select id="board-theme-select">
        ${BOARD_THEMES.map(t => `
          <option value="${t}" ${t === currentPrefs.board_theme ? "selected" : ""}>
            ${capitalise(t)}
          </option>`).join("")}
      </select>

      <label for="piece-set-select">Piece Set</label>
      <select id="piece-set-select">
        ${PIECE_SETS.map(p => `
          <option value="${p}" ${p === currentPrefs.piece_set ? "selected" : ""}>
            ${capitalise(p)}
          </option>`).join("")}
      </select>
    `;

    document.getElementById("board-theme-select").addEventListener("change", async e => {
      const theme = e.target.value;
      applyBoardTheme(theme);
      await savePrefs({ board_theme: theme, piece_set: getCurrentPieceSet() });
    });

    document.getElementById("piece-set-select").addEventListener("change", async e => {
      const pieceSet = e.target.value;
      applyPieceSet(pieceSet);
      await savePrefs({ board_theme: getCurrentBoardTheme(), piece_set: pieceSet });
    });
  }

  function getCurrentBoardTheme() {
    return document.getElementById("board-theme-select")?.value || "classic";
  }

  function getCurrentPieceSet() {
    return document.getElementById("piece-set-select")?.value || "classic";
  }

  function capitalise(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  // ── Bootstrap ────────────────────────────────────────────────────────────

  async function init() {
    const prefs = await loadPrefs();
    applyBoardTheme(prefs.board_theme);
    applyPieceSet(prefs.piece_set);
    buildPanel(prefs);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();