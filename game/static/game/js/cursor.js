const cursor = document.querySelector(".cursor");
const cursorDropdown = document.querySelector(".cursor-dropdown");
const cursorTrigger = document.querySelector(".cursor-btn");
const cursorTypeLabel = document.querySelector("#cursorTypeLabel");
const cursorOptions = document.querySelectorAll("[data-cursor]");

if (!cursor) {
    console.warn("Cursor element not found.");
} 
else {
const CURSOR_STORAGE_KEY = 'checkora:cursor-type';
      const VALID_CURSOR_TYPES = ['default', 'glow', 'trail', 'sparkle', 'orbit', 'chess'];

      // ── Accessibility / device guards ────────────────────────────────
      // Respect users who set the OS-level "reduce motion" preference.
      const prefersReducedMotion = window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      // Skip the custom cursor entirely on touch-only devices.
      const isTouchDevice = window.matchMedia &&
        window.matchMedia('(pointer: coarse)').matches;

      let activeCursor = 'default';
      let mouseX = 0;
      let mouseY = 0;
      let rafRunning = false;

      // ── Position update: compositor-only transform ──────────────────
      // This is the perf fix — writing left/top triggers layout every
      // frame. Writing transform: translate3d() stays on the compositor
      // (GPU layer) and gives 60+ FPS.
      //
      // The CSS positions the cursor at top:0; left:0 with width/height
      // matching its size. JS writes translate3d(mouseX, mouseY, 0) to
      // place the cursor's top-left corner at the mouse position. The
      // CSS-rendered size then naturally extends down/right from there.
      // (Earlier versions centered via translate(-50%, -50%) but that
      //  collided with CSS animations on pseudo-elements.)
      const CURSOR_OFFSETS = {
        default: 8,
        glow: 9,
        trail: 6,
        sparkle: 8,
        orbit: 20,
        chess: 12
      };
      let cursorOffset = CURSOR_OFFSETS.default;
      function updateCursorPosition() {
        cursor.style.transform =
          'translate3d(' + (mouseX - cursorOffset) + 'px, ' + (mouseY - cursorOffset) + 'px, 0)';
        rafRunning = false;
      }

      // mousemove only caches coords — no DOM writes here.
      document.addEventListener('mousemove', e => {
        mouseX = e.clientX;
        mouseY = e.clientY;
        if (!rafRunning && activeCursor !== 'default') {
          rafRunning = true;
          requestAnimationFrame(updateCursorPosition);
        }
      }, { passive: true });

      // ── localStorage helpers (safe — won't throw on disabled storage) ─
      function safeGetStoredType() {
        try {
          const v = window.localStorage.getItem(CURSOR_STORAGE_KEY);
          return VALID_CURSOR_TYPES.indexOf(v) >= 0 ? v : 'default';
        } catch (e) { return 'default'; }
      }
      function safeSetStoredType(type) {
        try { window.localStorage.setItem(CURSOR_STORAGE_KEY, type); } catch (e) { /* ignore */ }
      }

      // ── Apply a cursor type ─────────────────────────────────────────
      function updateCursorType(type, persist) {
        if (VALID_CURSOR_TYPES.indexOf(type) < 0) type = 'default';
        // Auto-fallback for reduced-motion users (override non-default picks).
        if ((isTouchDevice || prefersReducedMotion) && type !== 'default') type = 'default';

        activeCursor = type;
        cursorOffset = CURSOR_OFFSETS[type] || CURSOR_OFFSETS.default;
        cursor.className = 'cursor';

        if (type !== 'default') {
          cursor.classList.add(type);
          cursor.style.opacity = '0.98';
          cursor.style.display = type === 'chess' ? 'flex' : 'block';
        } else {
          cursor.style.opacity = '0';
          cursor.style.display = 'none';
        }

        if (cursorTypeLabel) {
            cursorTypeLabel.textContent =
                type.charAt(0).toUpperCase() + type.slice(1);
        }
        document.body.classList.toggle('hide-native-cursor', type !== 'default');
        if (cursorOptions.length) {
            cursorOptions.forEach(option => {
                option.classList.toggle(
                    "selected",
                    option.dataset.cursor === type
                );
            });
        }

        // Start/stop the rAF loop as needed.
        if (type !== 'default' && !rafRunning) {
          rafRunning = true;
          requestAnimationFrame(updateCursorPosition);
        }

        if (persist) safeSetStoredType(type);
      }

      // ── Init ────────────────────────────────────────────────────────
      if (!isTouchDevice) {
        const initialType = prefersReducedMotion ? 'default' : safeGetStoredType();
        updateCursorType(initialType, false);
      }
      window.updateCursorType = updateCursorType;

      // ── Dropdown wiring ─────────────────────────────────────────────
      if (cursorDropdown && cursorTrigger) {

    function closeCursorDropdown() {
        cursorDropdown.classList.remove("active");
        cursorTrigger.setAttribute("aria-expanded", "false");
    }

    cursorTrigger.addEventListener("click", e => {
        e.stopPropagation();
        cursorDropdown.classList.toggle("active");

        const expanded =
            cursorDropdown.classList.contains("active");

        cursorTrigger.setAttribute("aria-expanded", expanded);
    });

    cursorOptions.forEach(option => {
        option.addEventListener("click", () => {
            updateCursorType(option.dataset.cursor, true);
            closeCursorDropdown();
        });
    });

    document.addEventListener("click", e => {
        if (!cursorDropdown.contains(e.target)) {
            closeCursorDropdown();
        }
    });

    document.addEventListener("keydown", e => {
        if (e.key === "Escape") {
            closeCursorDropdown();
        }
    });

    window.addEventListener("scroll", closeCursorDropdown, {
        passive: true,
    });
}
    
}
  