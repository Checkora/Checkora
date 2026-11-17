// The performance tier. Loaded in <head> right after theme.js, so <html>
// carries data-perf="high" or data-perf="low" before anything is painted.
// "high" is the site as designed. "low" keeps every page and every control
// and drops the costly decoration: 3D scenes, blur, glows, long animations.
//
// How the tier is chosen:
//   1. ?perf=low or ?perf=high in the address wins and is remembered for the
//      browser session. ?perf=auto forgets it and starts again.
//   2. Otherwise a first guess from what the browser says about the machine:
//      the Save-Data setting, the number of cores and the memory, and the
//      name of the GPU. Reading that name means making a WebGL context,
//      which can take seconds on the very machines this is for, so it is
//      not done here in <head>. It is done once, the first time a page asks
//      for a 3D scene or has gone idle after loading, and kept for a week.
//   3. Then the page is watched while it animates. Three slow seconds move a
//      "high" machine down to "low" for the rest of the session.
// Nothing ever moves a machine back up on its own.
// prefers-reduced-motion is a separate setting and is left to the stylesheets.
(function() {
    'use strict';

    const root = document.documentElement;
    const OVERRIDE_KEY = 'checkora:perf';
    const DEMOTED_KEY = 'checkora:perf-demoted';
    const GPU_KEY = 'checkora:perf-gpu';
    const GPU_DAYS = 7;
    const EVENT = 'checkora:perf';

    // Storage can be blocked; every call is allowed to fail quietly.
    const storage = (area) => ({
        get(key) {
            try {
                return window[area].getItem(key);
            } catch (error) {
                return null;
            }
        },
        set(key, value) {
            try {
                window[area].setItem(key, value);
            } catch (error) {
                // The value then lasts for this page only.
            }
        },
        remove(key) {
            try {
                window[area].removeItem(key);
            } catch (error) {
                // Nothing was stored.
            }
        },
    });
    const session = storage('sessionStorage');
    const kept = storage('localStorage');
    const valid = (value) => (value === 'low' || value === 'high' ? value : null);

    /* ---------- the GPU ---------- */

    // Renderers that draw on the CPU.
    const SOFTWARE_GPU = /swiftshader|llvmpipe|softpipe|lavapipe|software|basic render|gdi generic/i;
    // Integrated graphics that are known to be slow. Deliberately short:
    // anything newer starts as "high" and the frame check decides.
    const WEAK_GPU = [
        /Intel\(R\) HD Graphics(?: Family)?(?! ?\d)/i, // Atom, and Pentium or Celeron before 2015
        /Intel\(R\) HD Graphics [2-6]\d{3}\b/i, // Sandy Bridge to Broadwell
        /Intel\(R\) HD Graphics (?:4\d\d|50\d|51[05]|61[05])\b/i, // Atom, Celeron and Core m
        /Intel\(R\) UHD Graphics 60[05]\b/i, // Gemini Lake Celeron and Pentium
        /\bGMA\b|Intel\(R\) [GQ]\d\d\b/i,
        /Radeon(?:\(TM\))? R[2-5] /i, // AMD A-series laptops
        /Mali-(?:4\d\d|T\d{3})\b/i,
        /Adreno \(TM\) (?:[2-4]\d\d|50\d)\b/i,
        /PowerVR (?:SGX|Rogue GE8)/i,
        /VideoCore/i,
    ];
    const GPU_CLASSES = ['software', 'weak', 'apple', 'fine', 'none'];

    // The GPU's name, '' if the browser will not say, or null without WebGL.
    function readRenderer() {
        try {
            const canvas = document.createElement('canvas');
            const options = { alpha: false, antialias: false, depth: false, stencil: false };
            const gl = canvas.getContext('webgl', options) || canvas.getContext('experimental-webgl', options);
            if (!gl) return null;
            const info = gl.getExtension('WEBGL_debug_renderer_info');
            const name = info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
            const lose = gl.getExtension('WEBGL_lose_context');
            if (lose) lose.loseContext();
            return String(name || '');
        } catch (error) {
            return null;
        }
    }

    function classify(renderer) {
        if (renderer === null) return 'none';
        if (SOFTWARE_GPU.test(renderer)) return 'software';
        if (/apple/i.test(renderer)) return 'apple';
        // Firefox reports one name for a whole family of chips, so a model
        // number there says little. Only a software renderer is believed.
        const bucketed = /Firefox\//.test(navigator.userAgent);
        if (!bucketed && WEAK_GPU.some((pattern) => pattern.test(renderer))) return 'weak';
        return 'fine';
    }

    const today = () => Math.floor(Date.now() / 864e5);
    function rememberedGpu() {
        const [name, day] = String(kept.get(GPU_KEY) || '').split('|');
        const age = today() - Number(day);
        return GPU_CLASSES.includes(name) && age >= 0 && age < GPU_DAYS ? name : null;
    }

    // The class of GPU: null until it has been looked at. gpu() looks.
    let chip = null;
    function gpu() {
        if (!chip) {
            chip = classify(readRenderer());
            kept.set(GPU_KEY, `${chip}|${today()}`);
        }
        return chip;
    }

    /* ---------- the first guess ---------- */

    function guess() {
        const connection = navigator.connection;
        if (connection && connection.saveData) return ['low', 'save-data'];
        if (chip === 'software') return ['low', 'software-gpu'];
        if (chip === 'weak') return ['low', 'weak-gpu'];

        // An Apple GPU is never guessed low, whatever the core count says.
        // Until the GPU has been looked at, the user agent stands in for it.
        const apple = chip ? chip === 'apple' : /Macintosh|iPhone|iPad/.test(navigator.userAgent);
        if (apple) return ['high', 'guess'];

        const cores = navigator.hardwareConcurrency || 0;
        const memory = navigator.deviceMemory || 0;
        // No WebGL at all usually means no GPU acceleration at all.
        if (chip === 'none' && ((cores && cores <= 4) || (memory && memory <= 4))) return ['low', 'no-gpu'];
        // Few cores together with little memory. Browsers that do not report
        // memory only count as weak with two cores or fewer.
        if (cores && memory && cores <= 4 && memory <= 4) return ['low', 'cores-and-memory'];
        if (cores && !memory && cores <= 2) return ['low', 'cores'];
        return ['high', 'guess'];
    }

    /* ---------- deciding ---------- */

    let asked = null;
    try {
        asked = new URLSearchParams(window.location.search).get('perf');
    } catch (error) {
        asked = null;
    }
    if (valid(asked)) {
        session.set(OVERRIDE_KEY, asked);
    } else if (asked === 'auto') {
        session.remove(OVERRIDE_KEY);
        session.remove(DEMOTED_KEY);
        kept.remove(GPU_KEY);
    }
    const override = valid(asked) || valid(session.get(OVERRIDE_KEY));
    chip = rememberedGpu();

    let tier;
    let reason;
    if (override) {
        tier = override;
        reason = 'override';
    } else if (session.get(DEMOTED_KEY) === '1') {
        tier = 'low';
        reason = 'frames';
    } else {
        [tier, reason] = guess();
    }
    root.setAttribute('data-perf', tier);

    /* ---------- moving down ---------- */

    const listeners = new Set();
    const watching = () => tier === 'high' && !override;

    // Applies "low" to a page that is already running and tells its effects.
    function demote(why, fps) {
        tier = 'low';
        reason = why;
        if (why === 'frames') session.set(DEMOTED_KEY, '1');
        root.setAttribute('data-perf', 'low');
        listeners.forEach((listener) => {
            try {
                listener();
            } catch (error) {
                // One effect failing to stand down must not stop the others.
            }
        });
        listeners.clear();
        document.dispatchEvent(new CustomEvent(EVENT, { detail: { tier: 'low', reason: why, fps } }));
    }

    // Finishes the first guess once the GPU's name is known.
    function lookAtGpu() {
        if (chip || !watching()) return;
        gpu();
        const [guessed, why] = guess();
        if (guessed === 'low') demote(why);
    }

    /* ---------- the frame check ---------- */

    // Frames are counted in one-second windows while something on the page
    // is moving: a 3D scene, a scroll, the pointer, a CSS animation or
    // transition that has just begun. A window under SLOW_FPS is a strike, a
    // good one takes a strike back, and three strikes demote.
    const SLOW_FPS = 40;
    const STRIKES = 3;
    const STALL_MS = 3000;
    // Chrome's Energy Saver and iOS Low Power Mode hold a strong machine at a
    // steady 30 frames a second. That is a cap, not lag, and the low tier
    // cannot lift it, so a window that ticks along evenly near 30 is skipped.
    const LONG_FRAME_MS = 40;
    const hasFrames = typeof window.requestAnimationFrame === 'function';
    let strikes = 0;
    let holds = 0;
    let busyUntil = 0;
    let settleUntil = Infinity;
    let request = 0;
    let windowStart = 0;
    let lastFrame = 0;
    let frames = 0;
    let longFrames = 0;
    let broken = false;

    function tick(now) {
        request = 0;
        if (!watching() || document.visibilityState !== 'visible') return;
        if (now < settleUntil || !windowStart) {
            windowStart = now;
            frames = 0;
            longFrames = 0;
            broken = false;
        } else {
            frames += 1;
            if (now - lastFrame > LONG_FRAME_MS) longFrames += 1;
            // A gap this long is the tab being stalled (a dialog, the
            // debugger, the laptop lid), not a slow frame.
            if (now - lastFrame > STALL_MS) broken = true;
            const length = now - windowStart;
            if (length >= 1000) {
                const fps = (frames * 1000) / length;
                const capped = fps > 26 && fps < 34 && longFrames <= frames * 0.1;
                if (!broken && !capped) {
                    strikes = fps < SLOW_FPS ? strikes + 1 : Math.max(0, strikes - 1);
                    if (strikes >= STRIKES) {
                        demote('frames', Math.round(fps));
                        return;
                    }
                }
                windowStart = now;
                frames = 0;
                longFrames = 0;
                broken = false;
            }
        }
        lastFrame = now;
        if (holds > 0 || now < busyUntil) request = window.requestAnimationFrame(tick);
        else windowStart = 0;
    }

    function wake() {
        if (!request && hasFrames && watching() && document.visibilityState === 'visible') {
            request = window.requestAnimationFrame(tick);
        }
    }
    function noteActivity() {
        if (!watching()) return;
        busyUntil = performance.now() + 1500;
        wake();
    }
    // Start a fresh window a moment from now: used after loading and after
    // the tab comes back, when slow frames say nothing about the machine.
    function settle(ms) {
        settleUntil = performance.now() + ms;
        windowStart = 0;
    }

    if (watching()) {
        const quiet = { passive: true, capture: true };
        ['scroll', 'pointermove', 'animationstart', 'transitionrun'].forEach((type) => {
            document.addEventListener(type, noteActivity, quiet);
        });
        document.addEventListener('visibilitychange', () => {
            settle(1000);
            wake();
        });
        window.addEventListener('resize', () => settle(500), { passive: true });
        const loaded = () => {
            settle(1000);
            noteActivity();
            // A page with no 3D scene never asks about the GPU, so it is
            // looked at here, once the page has nothing better to do.
            if (chip) return;
            if (window.requestIdleCallback) window.requestIdleCallback(lookAtGpu, { timeout: 4000 });
            else window.setTimeout(lookAtGpu, 1500);
        };
        if (document.readyState === 'complete') loaded();
        else window.addEventListener('load', loaded);
        window.addEventListener('pageshow', (event) => event.persisted && settle(1000));
    }

    // On the low tier a page change is a plain page change.
    ['pageswap', 'pagereveal'].forEach((type) => {
        window.addEventListener(type, (event) => {
            if (tier === 'low' && event.viewTransition) event.viewTransition.skipTransition();
        });
    });

    /* ---------- for the other scripts ---------- */

    window.checkoraPerf = {
        get tier() {
            return tier;
        },
        get low() {
            return tier === 'low';
        },
        // 'override', 'frames', or what the first guess went on.
        get reason() {
            return reason;
        },
        // True when the GPU is a software renderer. Looks at the GPU if
        // nothing has yet.
        get software() {
            return gpu() === 'software';
        },
        // Should a 3D scene be mounted here? kind is 'hero' for the landing
        // board and 'piece' for the single turning pieces. On the low tier
        // the pieces are left as flat images, and the landing board is too
        // when the GPU is a software renderer. This is the moment the GPU is
        // looked at, so the answer can come with a move down to "low".
        wants3D(kind) {
            lookAtGpu();
            if (tier === 'high') return true;
            return kind === 'hero' && gpu() !== 'software';
        },
        // Calls listener once if this page is moved down to "low" while it
        // is open. Returns a function that cancels the subscription.
        onDemote(listener) {
            if (!watching()) return () => {};
            listeners.add(listener);
            return () => listeners.delete(listener);
        },
        // A running scene holds the frame check open; call the returned
        // function when the scene stops.
        hold() {
            let held = true;
            holds += 1;
            wake();
            return () => {
                if (held) holds -= 1;
                held = false;
            };
        },
    };
})();
