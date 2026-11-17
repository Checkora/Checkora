// Shared by the community pages (forum, leaderboard, achievements, stats and
// match history): the turning 3D piece beside a page title, and numbers that
// count up when they scroll into view.

const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// A stage is <div class="piece-stage" data-piece="k" data-piece-color="w">
// holding a <canvas> and a flat SVG of the same piece. The SVG is what you
// see until the 3D piece is running, and what stays if WebGL is missing.
async function mountStages() {
    const stages = Array.from(document.querySelectorAll('.piece-stage[data-piece]'));
    if (!stages.length || !('IntersectionObserver' in window)) return;
    // On the low performance tier the flat pieces stay, and three.js is not
    // fetched at all.
    if (window.checkoraPerf?.wants3D('piece') === false) return;

    let scene;
    try {
        scene = await import('./scene3d.js');
    } catch (error) {
        return;
    }
    if (!scene.shouldMount3D('piece')) return;

    const mount = (stage) => {
        const canvas = stage.querySelector('canvas');
        // The page may have moved to the low tier since the first stage started.
        if (!canvas || window.checkoraPerf?.low) return;
        const flat = () => stage.classList.remove('is-live');
        try {
            scene.mountPiece(canvas, {
                type: stage.dataset.piece,
                color: stage.dataset.pieceColor || 'w',
                fallen: stage.hasAttribute('data-piece-fallen'),
                onFail: flat,
            });
            stage.classList.add('is-live');
        } catch (error) {
            flat();
        }
    };

    // A stage is only started once it is on screen, so a hidden one costs nothing.
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            observer.unobserve(entry.target);
            mount(entry.target);
        });
    }, { rootMargin: '120px' });
    stages.forEach((stage) => observer.observe(stage));
}

// data-count on an element (or on the wrapper of a .num) makes its number
// run up from zero. "+12", "64.5%" and "1200" all work; text is left alone.
function countUp() {
    const items = document.querySelectorAll('[data-count]');
    // On the low performance tier the numbers are simply there.
    const low = Boolean(window.checkoraPerf?.low);
    if (!items.length || calm || low || !('IntersectionObserver' in window)) return;

    const jobs = new Map();
    items.forEach((item) => {
        const target = item.querySelector('.num') || item;
        const match = target.textContent.trim().match(/^([^\d.-]*)(-?\d+(?:\.\d+)?)(.*)$/s);
        if (!match) return;
        const end = Number(match[2]);
        if (!Number.isFinite(end) || end === 0) return;
        const decimals = (match[2].split('.')[1] || '').length;
        const write = (value) => {
            target.textContent = `${match[1]}${value.toFixed(decimals)}${match[3]}`;
        };
        write(0);
        jobs.set(item, { end, write });
    });

    const run = ({ end, write }) => {
        const length = 900 + Math.min(600, Math.abs(end) * 2);
        let start = 0;
        const frame = (now) => {
            start = start || now;
            const t = Math.min(1, (now - start) / length);
            write(end * (1 - Math.pow(1 - t, 3)));
            if (t < 1) requestAnimationFrame(frame);
            else write(end);
        };
        requestAnimationFrame(frame);
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            observer.unobserve(entry.target);
            run(jobs.get(entry.target));
        });
    }, { threshold: 0.4 });
    jobs.forEach((job, item) => observer.observe(item));
}

countUp();
mountStages();
