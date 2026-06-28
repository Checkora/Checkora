(function() {
    let canvas = null;
    let ctx = null;
    let particles = [];
    let animationId = null;
    let isAnimating = false;

    function initCanvas() {
        if (!canvas) {
            canvas = document.createElement('canvas');
            canvas.style.position = 'fixed';
            canvas.style.top = '0';
            canvas.style.left = '0';
            canvas.style.width = '100vw';
            canvas.style.height = '100vh';
            canvas.style.pointerEvents = 'none';
            canvas.style.zIndex = '9999';
            document.body.appendChild(canvas);
            
            ctx = canvas.getContext('2d');
            
            window.addEventListener('resize', resizeCanvas);
            resizeCanvas();
        }
    }

    function resizeCanvas() {
        if (canvas) {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
    }

    function destroyCanvas() {
        if (canvas && particles.length === 0) {
            window.removeEventListener('resize', resizeCanvas);
            if (canvas.parentNode) {
                canvas.parentNode.removeChild(canvas);
            }
            canvas = null;
            ctx = null;
        }
    }

    function randomInRange(min, max) {
        return Math.random() * (max - min) + min;
    }

    function createParticles(options) {
        // Cap maximum particles to prevent performance issues on spam clicks
        if (particles.length > 1000) return;
        
        const count = options.count ?? 100;
        const spread = options.spread ?? 70;
        const colors = options.colors?.length ? options.colors : ['#26ccff', '#a25afd', '#ff5e7e', '#88ff5a', '#fcff42', '#ffa62d', '#ff36ff'];
        const shapes = options.shapes?.length ? options.shapes : ['square', 'circle'];
        const originX = options.origin?.x ?? 0.5;
        const originY = options.origin?.y ?? 0.6; // default slightly lower than center
        const angle = options.angle ?? 90;
        const velocity = options.startVelocity ?? 45;
        const decay = options.decay ?? 0.9;
        const gravity = options.gravity ?? 1;
        const scalar = options.scalar ?? 1;
        
        for (let i = 0; i < count; i++) {
            const radAngle = angle * (Math.PI / 180);
            const radSpread = spread * (Math.PI / 180);
            
            const pAngle = radAngle + (Math.random() * radSpread - radSpread / 2);
            const pVelocity = velocity * (0.5 + Math.random() * 0.5);

            particles.push({
                x: originX * canvas.width,
                y: originY * canvas.height,
                w: randomInRange(5, 10) * scalar,
                h: randomInRange(5, 15) * scalar,
                color: colors[Math.floor(Math.random() * colors.length)],
                shape: shapes[Math.floor(Math.random() * shapes.length)],
                vx: Math.cos(pAngle) * pVelocity,
                vy: -Math.sin(pAngle) * pVelocity,
                gravity: gravity,
                friction: decay,
                rotation: randomInRange(0, 360),
                rotationSpeed: randomInRange(-10, 10)
            });
        }
    }

    function update() {
        if (particles.length === 0) {
            isAnimating = false;
            destroyCanvas();
            return;
        }

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (let i = particles.length - 1; i >= 0; i--) {
            let p = particles[i];

            p.vx *= p.friction;
            p.vy *= p.friction;
            p.vy += p.gravity;
            p.x += p.vx;
            p.y += p.vy;
            p.rotation += p.rotationSpeed;

            if (p.y > canvas.height + 100 || p.y < -100 || p.x < -100 || p.x > canvas.width + 100) {
                particles.splice(i, 1);
                continue;
            }

            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate((p.rotation * Math.PI) / 180);
            ctx.fillStyle = p.color;

            if (p.shape === 'circle') {
                ctx.beginPath();
                ctx.arc(0, 0, p.w / 2, 0, 2 * Math.PI);
                ctx.fill();
            } else {
                ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
            }

            ctx.restore();
        }

        if (isAnimating) {
            animationId = requestAnimationFrame(update);
        }
    }

    window.triggerConfetti = function(options = {}) {
        // Respect reduced motion preference
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return;
        }

        initCanvas();
        createParticles(options);

        if (!isAnimating) {
            isAnimating = true;
            update();
        }
    };
})();
