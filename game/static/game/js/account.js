// Account pages: the piece that turns beside the form, and the profile
// numbers that count up when they come into view.

const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// The stylesheet hides the stage on narrow screens, so three.js is only
// fetched once the window is wide enough for the stage to be shown.
function startStage(stage) {
    const canvas = stage.querySelector('canvas[data-piece]');
    if (!canvas) return;
    const flat = () => {
        stage.classList.remove('is-live');
        stage.classList.add('is-flat');
    };
    let started = false;

    async function start() {
        if (started || stage.offsetWidth === 0) return;
        started = true;
        window.removeEventListener('resize', start);
        // On the low performance tier the flat piece is the piece, and
        // three.js is not fetched at all.
        if (window.checkoraPerf?.wants3D('piece') === false) {
            flat();
            return;
        }
        try {
            const { shouldMount3D, mountPiece } = await import('./scene3d.js');
            if (!shouldMount3D('piece')) {
                flat();
                return;
            }
            mountPiece(canvas, {
                type: canvas.dataset.piece,
                color: canvas.dataset.pieceColor || 'w',
                fallen: canvas.dataset.pieceFallen !== undefined,
                onFail: flat,
            });
            stage.classList.add('is-live');
        } catch (error) {
            flat();
        }
    }

    window.addEventListener('resize', start);
    start();
}

// The number stays in the page for screen readers; only a copy counts up.
function countUp(element) {
    const target = Number(element.textContent.trim());
    // On the low performance tier the number is simply there.
    const low = Boolean(window.checkoraPerf?.low);
    if (calm || low || !Number.isFinite(target) || target <= 0) return;

    const real = document.createElement('span');
    real.className = 'sr-only';
    real.textContent = element.textContent.trim();
    const shown = document.createElement('span');
    shown.setAttribute('aria-hidden', 'true');
    shown.textContent = '0';
    element.replaceChildren(shown, real);

    const run = () => {
        const began = performance.now();
        const step = (now) => {
            const t = Math.min(1, (now - began) / 1100);
            shown.textContent = Math.round(target * (1 - Math.pow(1 - t, 3)));
            if (t < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
    };
    const observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
            observer.disconnect();
            run();
        }
    });
    observer.observe(element);
}

document.querySelectorAll('.stage').forEach(startStage);
document.querySelectorAll('[data-count]').forEach(countUp);
