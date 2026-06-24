/**
 * Checkora Confetti Celebration System
 * Canvas-based particle burst for achievements, level-ups, puzzle completions.
 * Usage: window.triggerConfetti({ count: 150, spread: 80, origin: { x: 0.5, y: 0.5 } })
 */
(function () {
    'use strict';

    const DEFAULTS = {
        count: 120,
        spread: 70,
        origin: { x: 0.5, y: 0.5 },
        colors: ['#ffd700', '#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#ff9ff3', '#54a0ff'],
        shapes: ['square', 'circle', 'triangle'],
        speed: { min: 4, max: 12 },
        size: { min: 4, max: 10 },
        rotation: { min: -180, max: 180 },
        drift: { min: -2, max: 2 },
        gravity: 0.15,
        decay: { min: 0.015, max: 0.03 },
        canvasId: 'confetti-canvas',
        duration: 3000,
    };

    let canvas, ctx, particles, animationId, active = false;

    function createCanvas() {
        let existing = document.getElementById(DEFAULTS.canvasId);
        if (existing) existing.remove();
        canvas = document.createElement('canvas');
        canvas.id = DEFAULTS.canvasId;
        canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:2147483647;';
        document.body.appendChild(canvas);
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        ctx = canvas.getContext('2d');
    }

    function randomRange(min, max) {
        return Math.random() * (max - min) + min;
    }

    function createParticle(origin, opts) {
        const angle = randomRange(0, Math.PI * 2);
        const speed = randomRange(opts.speed.min, opts.speed.max);
        const color = opts.colors[Math.floor(Math.random() * opts.colors.length)];
        const shape = opts.shapes[Math.floor(Math.random() * opts.shapes.length)];
        const size = randomRange(opts.size.min, opts.size.max);
        const drift = randomRange(opts.drift.min, opts.drift.max);
        const rotation = randomRange(opts.rotation.min, opts.rotation.max);
        const rotationSpeed = randomRange(-5, 5);
        const decay = randomRange(opts.decay.min, opts.decay.max);

        return {
            x: origin.x * canvas.width,
            y: origin.y * canvas.height,
            vx: Math.cos(angle) * speed + drift,
            vy: Math.sin(angle) * speed - 4,
            color,
            shape,
            size,
            rotation,
            rotationSpeed,
            opacity: 1,
            decay,
            gravity: opts.gravity,
            wobble: Math.random() * Math.PI * 2,
            wobbleSpeed: randomRange(0.02, 0.08),
        };
    }

    function drawParticle(p) {
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate((p.rotation * Math.PI) / 180);
        ctx.globalAlpha = p.opacity;
        ctx.fillStyle = p.color;

        if (p.shape === 'circle') {
            ctx.beginPath();
            ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
            ctx.fill();
        } else if (p.shape === 'triangle') {
            const s = p.size / 2;
            ctx.beginPath();
            ctx.moveTo(0, -s);
            ctx.lineTo(-s, s);
            ctx.lineTo(s, s);
            ctx.closePath();
            ctx.fill();
        } else {
            ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
        }
        ctx.restore();
    }

    function animate() {
        if (!canvas || !ctx) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        let alive = false;
        for (const p of particles) {
            p.wobble += p.wobbleSpeed;
            p.vx += Math.sin(p.wobble) * 0.1;
            p.vy += p.gravity;
            p.x += p.vx;
            p.y += p.vy;
            p.rotation += p.rotationSpeed;
            p.opacity -= p.decay;

            if (p.opacity > 0) {
                drawParticle(p);
                alive = true;
            }
        }

        if (alive) {
            animationId = requestAnimationFrame(animate);
        } else {
            cleanup();
        }
    }

    function cleanup() {
        if (animationId) {
            cancelAnimationFrame(animationId);
            animationId = null;
        }
        if (canvas && canvas.parentNode) {
            canvas.parentNode.removeChild(canvas);
        }
        canvas = null;
        ctx = null;
        particles = [];
        active = false;
    }

    function triggerConfetti(userOpts) {
        if (active) cleanup();
        active = true;
        const opts = { ...DEFAULTS };
        if (userOpts) {
            Object.keys(userOpts).forEach(k => {
                if (k === 'origin' && userOpts.origin) {
                    opts.origin = { ...DEFAULTS.origin, ...userOpts.origin };
                } else {
                    opts[k] = userOpts[k];
                }
            });
        }
        createCanvas();
        particles = [];
        for (let i = 0; i < opts.count; i++) {
            particles.push(createParticle(opts.origin, opts));
        }
        animate();

        if (opts.duration > 0) {
            setTimeout(cleanup, opts.duration);
        }
    }

    // Expose to window
    window.triggerConfetti = triggerConfetti;

    // Auto-fire confetti for data-confetti elements
    document.addEventListener('DOMContentLoaded', function () {
        const targets = document.querySelectorAll('[data-confetti]');
        targets.forEach(el => {
            el.addEventListener('click', function (e) {
                const raw = this.dataset.confetti;
                let opts = {};
                try { opts = JSON.parse(raw); } catch (_) { /**/ }
                triggerConfetti(opts);
            });
        });

        // Fire on page if confetti-onload meta exists
        const meta = document.querySelector('meta[name="confetti-onload"]');
        if (meta) {
            const delay = parseInt(meta.getAttribute('data-delay')) || 500;
            setTimeout(triggerConfetti, delay);
        }
    });

    // Handle window resize
    window.addEventListener('resize', function () {
        if (canvas) {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
    });
})();
