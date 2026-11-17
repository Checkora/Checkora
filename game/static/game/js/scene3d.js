// Checkora's 3D scenes: the board on the landing page, which replays a
// famous game, and the single turning piece used on smaller pages.
// The chess set is built in code, so there are no model files to load.
//
// perf.js sorts machines into a "high" and a "low" tier. On the low tier the
// landing board is drawn more cheaply and the single pieces are not drawn at
// all; shouldMount3D() is how a page asks which it is getting.
import * as THREE from 'three';
import { RoomEnvironment } from '../vendor/three/RoomEnvironment.js';

const FILES = 'abcdefgh';
const BACK_RANK = ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'];

// Morphy v. the Duke of Brunswick and Count Isouard, Paris 1858.
const OPERA_GAME = [
    ['e2e4', 'e4'], ['e7e5', 'e5'], ['g1f3', 'Nf3'], ['d7d6', 'd6'], ['d2d4', 'd4'], ['c8g4', 'Bg4'],
    ['d4e5', 'dxe5'], ['g4f3', 'Bxf3'], ['d1f3', 'Qxf3'], ['d6e5', 'dxe5'], ['f1c4', 'Bc4'], ['g8f6', 'Nf6'],
    ['f3b3', 'Qb3'], ['d8e7', 'Qe7'], ['b1c3', 'Nc3'], ['c7c6', 'c6'], ['c1g5', 'Bg5'], ['b7b5', 'b5'],
    ['c3b5', 'Nxb5'], ['c6b5', 'cxb5'], ['c4b5', 'Bxb5+'], ['b8d7', 'Nbd7'], ['e1c1', 'O-O-O'], ['a8d8', 'Rd8'],
    ['d1d7', 'Rxd7'], ['d8d7', 'Rxd7'], ['h1d1', 'Rd1'], ['e7e6', 'Qe6'], ['b5d7', 'Bxd7+'], ['f6d7', 'Nxd7'],
    ['b3b8', 'Qb8+'], ['d7b8', 'Nxb8'], ['d1d8', 'Rd8#'],
];

// Half-outlines turned on a lathe. Units are board squares.
const PROFILES = {
    p: [[0, 0], [0.27, 0], [0.28, 0.05], [0.2, 0.1], [0.13, 0.16], [0.1, 0.36], [0.16, 0.42], [0.08, 0.46], [0.15, 0.56], [0.16, 0.64], [0.1, 0.73], [0, 0.76]],
    r: [[0, 0], [0.3, 0], [0.31, 0.06], [0.23, 0.12], [0.19, 0.2], [0.17, 0.5], [0.24, 0.56], [0.24, 0.74], [0.16, 0.74], [0.16, 0.66], [0, 0.66]],
    b: [[0, 0], [0.29, 0], [0.3, 0.06], [0.21, 0.12], [0.13, 0.2], [0.1, 0.5], [0.17, 0.56], [0.09, 0.6], [0.15, 0.72], [0.13, 0.84], [0.05, 0.95], [0.07, 0.99], [0, 1.02]],
    q: [[0, 0], [0.31, 0], [0.32, 0.06], [0.23, 0.13], [0.15, 0.22], [0.11, 0.62], [0.2, 0.68], [0.1, 0.72], [0.19, 0.9], [0.21, 1], [0.13, 0.98], [0.09, 1.06], [0, 1.1]],
    k: [[0, 0], [0.32, 0], [0.33, 0.06], [0.24, 0.13], [0.16, 0.22], [0.12, 0.66], [0.21, 0.72], [0.11, 0.76], [0.18, 0.96], [0.2, 1.04], [0.06, 1.06], [0.06, 1.2], [0, 1.22]],
};
const KNIGHT_OUTLINE = [
    [-0.3, 0], [0.3, 0], [0.3, 0.1], [0.22, 0.16], [0.26, 0.5], [0.2, 0.82], [0.08, 1], [0.02, 0.88], [-0.12, 0.84],
    [-0.34, 0.62], [-0.36, 0.5], [-0.26, 0.44], [-0.1, 0.52], [-0.04, 0.42], [-0.18, 0.22], [-0.24, 0.16], [-0.3, 0.1],
];

// The tier perf.js chose. Without perf.js everything runs as "high".
const tier = () => window.checkoraPerf;
const onLowTier = () => Boolean(tier()?.low);
// The landing board's frame rate on the low tier.
const LOW_FPS = 30;

const clamp01 = (value) => Math.min(1, Math.max(0, value));
const smooth = (t) => t * t * (3 - 2 * t);
const outBack = (t) => 1 + 2.4 * Math.pow(t - 1, 3) + 1.4 * Math.pow(t - 1, 2);
const squareIndex = (name) => FILES.indexOf(name[0]) + (Number(name[1]) - 1) * 8;
const squareX = (index) => (index % 8) - 3.5;
const squareZ = (index) => 3.5 - Math.floor(index / 8);

function buildGeometry(segments = 40) {
    const set = {};
    for (const [type, profile] of Object.entries(PROFILES)) {
        set[type] = new THREE.LatheGeometry(profile.map(([x, y]) => new THREE.Vector2(x, y)), segments);
    }
    const shape = new THREE.Shape();
    shape.moveTo(...KNIGHT_OUTLINE[0]);
    KNIGHT_OUTLINE.slice(1).forEach((point) => shape.lineTo(...point));
    shape.closePath();
    set.n = new THREE.ExtrudeGeometry(shape, { depth: 0.26, bevelEnabled: true, bevelThickness: 0.04, bevelSize: 0.03, bevelSegments: 3 });
    set.n.translate(0, 0, -0.13);
    set.n.scale(0.84, 0.84, 0.84);
    return set;
}

function buildMaterials() {
    return {
        w: new THREE.MeshPhysicalMaterial({ color: 0xf3ead6, metalness: 0, roughness: 0.3, clearcoat: 0.7, clearcoatRoughness: 0.22 }),
        b: new THREE.MeshPhysicalMaterial({ color: 0x101014, metalness: 0.55, roughness: 0.16, clearcoat: 1, clearcoatRoughness: 0.08 }),
    };
}

function startingPieces() {
    const pieces = [];
    for (let file = 0; file < 8; file++) {
        pieces.push({ type: BACK_RANK[file], color: 'w', square: file });
        pieces.push({ type: 'p', color: 'w', square: 8 + file });
        pieces.push({ type: 'p', color: 'b', square: 48 + file });
        pieces.push({ type: BACK_RANK[file], color: 'b', square: 56 + file });
    }
    return pieces;
}

// low: one canvas pixel per CSS pixel, no antialiasing and no shadow maps.
function createRenderer(canvas, low = false) {
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: !low, alpha: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(low ? 1 : Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = !low;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    return renderer;
}

function lightScene(scene, renderer, low = false) {
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.55;
    pmrem.dispose();

    const key = new THREE.DirectionalLight(0xfff1dc, 3.4);
    key.position.set(-5, 11, 6);
    key.castShadow = !low;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.bias = -0.0005;
    Object.assign(key.shadow.camera, { left: -8, right: 8, top: 8, bottom: -8, near: 1, far: 40 });
    scene.add(key);

    const rim = new THREE.DirectionalLight(0xffc253, 2.2);
    rim.position.set(7, 4, -9);
    scene.add(rim);
    scene.add(new THREE.HemisphereLight(0x8d8576, 0x050506, 0.7));
    return key;
}

// Runs the frame loop only while the canvas is on screen and the tab is open.
// maxFps() may return a frame rate to hold the loop to; 0 means every frame.
// While the loop runs it keeps perf.js counting frames.
function runLoop(canvas, frame, maxFps = () => 0) {
    let visible = true;
    let running = false;
    let last = 0;
    let handle = 0;
    let release = null;
    const tick = (now) => {
        handle = 0;
        if (!running) return;
        const cap = maxFps();
        // Two milliseconds of slack, so a 60 Hz screen draws every other frame.
        if (!cap || now - last >= 1000 / cap - 2) {
            const delta = Math.min(0.05, (now - last) / 1000);
            last = now;
            frame(delta, now / 1000);
        }
        handle = requestAnimationFrame(tick);
    };
    const update = () => {
        const wanted = visible && document.visibilityState === 'visible';
        if (wanted && !running) {
            running = true;
            last = performance.now();
            handle = requestAnimationFrame(tick);
            release = tier()?.hold() || null;
        } else if (!wanted && running) {
            running = false;
            release?.();
            release = null;
        }
    };
    const observer = new IntersectionObserver((entries) => {
        visible = entries.some((entry) => entry.isIntersecting);
        update();
    });
    observer.observe(canvas);
    document.addEventListener('visibilitychange', update);
    update();
    return () => {
        running = false;
        release?.();
        release = null;
        if (handle) cancelAnimationFrame(handle);
        observer.disconnect();
        document.removeEventListener('visibilitychange', update);
    };
}

function fit(renderer, camera, canvas, after) {
    const resize = () => {
        const width = canvas.clientWidth || 1;
        const height = canvas.clientHeight || 1;
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        after?.(width, height);
        camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();
    return () => observer.disconnect();
}

/**
 * The landing page board. It sets up the pieces, replays the Opera Game
 * move by move, tips the mated king over and starts again.
 * options.onPly({ ply, san, total }) is called as each move is played.
 */
export function mountHero(canvas, options = {}) {
    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    // On the low tier: one pixel per CSS pixel, no antialiasing, no shadow
    // maps, pieces turned with half as many faces, no light under the
    // pointer and half the frame rate.
    let low = onLowTier();
    const renderer = createRenderer(canvas, low);
    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x08080a, 17, 34);
    const keyLight = lightScene(scene, renderer, low);

    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 120);
    // On a wide screen the board sits right of centre, clear of the headline.
    const stopFit = fit(renderer, camera, canvas, (width, height) => {
        if (width / height > 1.15) camera.setViewOffset(width, height, -width * 0.19, 0, width, height);
        else camera.clearViewOffset();
    });

    // Board: 64 tiles on a slab with a gold edge.
    const tiles = new THREE.InstancedMesh(
        new THREE.BoxGeometry(0.97, 0.16, 0.97),
        new THREE.MeshStandardMaterial({ roughness: 0.42, metalness: 0.15 }),
        64,
    );
    tiles.receiveShadow = true;
    const LIGHT = new THREE.Color(0xc9b188);
    const DARK = new THREE.Color(0x3a2f24);
    const GOLD = new THREE.Color(0xf2b93b);
    scene.add(tiles);

    const slab = new THREE.Mesh(
        new THREE.BoxGeometry(8.7, 0.3, 8.7),
        new THREE.MeshPhysicalMaterial({ color: 0x0c0c10, metalness: 0.7, roughness: 0.25, clearcoat: 1 }),
    );
    slab.position.y = -0.2;
    slab.receiveShadow = true;
    scene.add(slab);
    const trim = new THREE.Mesh(new THREE.BoxGeometry(8.86, 0.06, 8.86), new THREE.MeshStandardMaterial({ color: 0xf0b13a, metalness: 1, roughness: 0.25 }));
    trim.position.y = -0.33;
    scene.add(trim);

    const floor = new THREE.Mesh(new THREE.PlaneGeometry(120, 120), new THREE.MeshStandardMaterial({ color: 0x050506, roughness: 0.9, metalness: 0 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.37;
    floor.receiveShadow = true;
    scene.add(floor);

    // The floor and the fog take the page's own colour, so the board stands
    // on the page in the light theme as well as the dark one.
    const PAGE_COLOUR = { dark: 0x08080a, light: 0xf5f0e4 };
    const FLOOR_COLOUR = { dark: 0x050506, light: 0xebe3d1 };
    function paintForTheme() {
        const theme = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
        scene.fog.color.setHex(PAGE_COLOUR[theme]);
        floor.material.color.setHex(FLOOR_COLOUR[theme]);
    }
    paintForTheme();
    document.addEventListener('checkora:theme', paintForTheme);

    const cursorLight = new THREE.PointLight(0xffd38a, 0, 9, 1.6);
    if (!low) scene.add(cursorLight);

    // Pieces.
    const geometry = buildGeometry(low ? 20 : 40);
    const materials = buildMaterials();
    const pieces = startingPieces().map((piece, order) => {
        const mesh = new THREE.Mesh(geometry[piece.type], materials[piece.color]);
        mesh.castShadow = true;
        if (piece.type === 'n') mesh.rotation.y = piece.color === 'w' ? -Math.PI / 2 : Math.PI / 2;
        scene.add(mesh);
        return {
            ...piece, mesh, order, home: piece.square, alive: true,
            from: new THREE.Vector3(), to: new THREE.Vector3(), t: 1, travel: 0.5,
            scale: 0, fallen: 0, hop: 0,
        };
    });
    const at = (square) => pieces.find((piece) => piece.alive && piece.square === square);

    const state = { clock: 0, ply: 0, nextAt: calm ? Infinity : 2.6, resetAt: Infinity, intro: 0, mated: null, lastFrom: -1, lastTo: -1 };
    const tileLift = new Float32Array(64);
    const tileGlow = new Float32Array(64);
    const ripple = { at: -10, x: 0, z: 0 };
    const pointer = { x: 0, y: 0, tx: 0, ty: 0, hover: -1, inside: false };
    let scroll = 0;

    function place(piece, square) {
        piece.square = square;
        piece.to.set(squareX(square), 0.08, squareZ(square));
        piece.from.copy(piece.to);
        piece.t = 1;
    }

    function setUp() {
        pieces.forEach((piece) => {
            piece.alive = true;
            piece.fallen = 0;
            place(piece, piece.home);
        });
        Object.assign(state, { ply: 0, mated: null, lastFrom: -1, lastTo: -1, intro: 0 });
        options.onPly?.({ ply: 0, san: '', total: OPERA_GAME.length });
    }

    function send(piece, square) {
        piece.from.copy(piece.mesh.position);
        piece.from.y = 0.08;
        piece.square = square;
        piece.to.set(squareX(square), 0.08, squareZ(square));
        piece.travel = 0.42 + piece.from.distanceTo(piece.to) * 0.05;
        piece.t = 0;
    }

    function play(instant) {
        const [move, san] = OPERA_GAME[state.ply];
        const from = squareIndex(move.slice(0, 2));
        const to = squareIndex(move.slice(2, 4));
        const mover = at(from);
        const taken = at(to);
        if (taken) taken.alive = false;
        if (instant) place(mover, to);
        else send(mover, to);
        // Castling long: the rook comes round to d1.
        if (mover.type === 'k' && Math.abs(to - from) === 2) {
            const rook = at(to < from ? from - 4 : from + 3);
            const rookTo = to < from ? from - 1 : from + 1;
            if (instant) place(rook, rookTo);
            else send(rook, rookTo);
        }
        state.lastFrom = from;
        state.lastTo = to;
        state.ply += 1;
        options.onPly?.({ ply: state.ply, san, total: OPERA_GAME.length });
        if (state.ply === OPERA_GAME.length) {
            state.mated = pieces.find((piece) => piece.alive && piece.type === 'k' && piece.color === 'b');
            state.resetAt = state.clock + 5.5;
            state.nextAt = Infinity;
        }
    }

    setUp();
    if (calm) {
        // No animation: show the position after White castles.
        state.intro = 10;
        for (let i = 0; i < 23; i++) play(true);
    }

    const ray = new THREE.Raycaster();
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -0.16);
    const hit = new THREE.Vector3();
    const ndc = new THREE.Vector2();

    function onMove(event) {
        const box = canvas.getBoundingClientRect();
        pointer.inside = event.clientX >= box.left && event.clientX <= box.right && event.clientY >= box.top && event.clientY <= box.bottom;
        ndc.set(((event.clientX - box.left) / box.width) * 2 - 1, -((event.clientY - box.top) / box.height) * 2 + 1);
        pointer.tx = ndc.x;
        pointer.ty = ndc.y;
        ray.setFromCamera(ndc, camera);
        pointer.hover = -1;
        if (pointer.inside && ray.ray.intersectPlane(plane, hit)) {
            const file = Math.round(hit.x + 3.5);
            const rank = Math.round(3.5 - hit.z);
            if (file >= 0 && file < 8 && rank >= 0 && rank < 8) pointer.hover = file + rank * 8;
        }
    }
    function onDown(event) {
        onMove(event);
        if (pointer.hover < 0 || calm) return;
        ripple.at = state.clock;
        ripple.x = squareX(pointer.hover);
        ripple.z = squareZ(pointer.hover);
        const piece = at(pointer.hover);
        if (piece) piece.hop = 1;
        options.onTap?.(FILES[pointer.hover % 8] + (Math.floor(pointer.hover / 8) + 1));
    }
    function onScroll() {
        scroll = clamp01(window.scrollY / Math.max(1, window.innerHeight * 0.9));
    }
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', onDown, { passive: true });
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    const dummy = new THREE.Object3D();
    const colour = new THREE.Color();
    const narrow = () => camera.aspect < 0.9;

    // On the low tier the board watches its own frame rate. Under 20 frames
    // a second for three seconds and it gives way to the page's flat board,
    // which costs nothing to show.
    const pace = { since: 0, last: 0, frames: 0 };
    function tooSlow(now) {
        if (now - pace.last > 0.5) {
            // The loop has just started, or was paused off screen.
            pace.since = now;
            pace.frames = 0;
        }
        pace.last = now;
        pace.frames += 1;
        if (now - pace.since < 3) return false;
        const slow = pace.frames / (now - pace.since) < 20;
        pace.since = now;
        pace.frames = 0;
        return slow;
    }

    function frame(delta, now) {
        if (low && tooSlow(now)) {
            giveUp();
            return;
        }
        state.clock += delta;
        state.intro += delta;
        if (state.clock >= state.nextAt) {
            play(false);
            if (state.nextAt !== Infinity) state.nextAt = state.clock + 1.55;
        }
        if (state.clock >= state.resetAt) {
            state.resetAt = Infinity;
            state.nextAt = state.clock + 2.8;
            setUp();
        }

        pointer.x += (pointer.tx - pointer.x) * Math.min(1, delta * 4);
        pointer.y += (pointer.ty - pointer.y) * Math.min(1, delta * 4);

        // Camera: a slow sweep, nudged by the pointer, pulling up as the page scrolls.
        const sweep = calm ? 0 : Math.sin(now * 0.11) * 0.42;
        const azimuth = 0.62 + sweep + pointer.x * 0.22;
        const radius = (narrow() ? 21 : 17.4) + scroll * 7;
        const height = (narrow() ? 12 : 9.2) - pointer.y * 1.1 + scroll * 9;
        camera.position.set(Math.sin(azimuth) * radius, height, Math.cos(azimuth) * radius);
        camera.lookAt(0, 0.4, 0);

        // Tiles: the hovered one lifts, a tap sends a ring across the board.
        const rippleAge = state.clock - ripple.at;
        for (let i = 0; i < 64; i++) {
            const x = squareX(i);
            const z = squareZ(i);
            let lift = i === pointer.hover ? 0.16 : 0;
            if (rippleAge < 2.2) {
                const reach = rippleAge * 7 - Math.hypot(x - ripple.x, z - ripple.z);
                if (reach > 0 && reach < 2.4) lift += Math.sin((reach / 2.4) * Math.PI) * 0.34 * (1 - rippleAge / 2.2);
            }
            tileLift[i] += (lift - tileLift[i]) * Math.min(1, delta * 12);
            const glow = i === state.lastFrom || i === state.lastTo ? 1 : i === pointer.hover ? 0.55 : 0;
            tileGlow[i] += (glow - tileGlow[i]) * Math.min(1, delta * 6);

            const landed = calm ? 1 : outBack(clamp01((state.intro - (i % 8 + Math.floor(i / 8)) * 0.035) / 0.7));
            dummy.position.set(x, tileLift[i] - (1 - landed) * 1.6, z);
            dummy.scale.setScalar(Math.max(0.001, landed));
            dummy.updateMatrix();
            tiles.setMatrixAt(i, dummy.matrix);
            colour.copy((i % 8 + Math.floor(i / 8)) % 2 ? LIGHT : DARK).lerp(GOLD, tileGlow[i] * 0.6);
            tiles.setColorAt(i, colour);
        }
        tiles.instanceMatrix.needsUpdate = true;
        tiles.instanceColor.needsUpdate = true;

        // The light under the pointer. The low tier goes without it; the
        // hovered tile still lifts and turns gold.
        if (low) {
            cursorLight.intensity = 0;
        } else if (pointer.hover >= 0) {
            cursorLight.position.set(squareX(pointer.hover), 2.2, squareZ(pointer.hover));
            cursorLight.intensity += (16 - cursorLight.intensity) * Math.min(1, delta * 6);
        } else {
            cursorLight.intensity += (0 - cursorLight.intensity) * Math.min(1, delta * 6);
        }

        for (const piece of pieces) {
            const { mesh } = piece;
            if (piece.t < 1) piece.t = Math.min(1, piece.t + delta / piece.travel);
            const e = smooth(piece.t);
            const arc = Math.sin(e * Math.PI) * (piece.type === 'n' ? 1.25 : 0.38 + piece.from.distanceTo(piece.to) * 0.07);
            mesh.position.lerpVectors(piece.from, piece.to, e);
            mesh.position.y += arc + tileLift[piece.square] * (piece.t === 1 ? 1 : 0);

            piece.hop = Math.max(0, piece.hop - delta * 1.8);
            mesh.position.y += Math.sin((1 - piece.hop) * Math.PI) * piece.hop * 1.1;

            // Pieces drop in rank by rank at the start, and shrink away when taken.
            const dropped = calm ? 1 : clamp01((state.intro - 0.75 - piece.order * 0.03) / 0.5);
            const wanted = piece.alive ? outBack(dropped) : 0;
            piece.scale += (wanted - piece.scale) * Math.min(1, delta * (piece.alive ? 14 : 7));
            mesh.position.y += (1 - smooth(dropped)) * 6;
            mesh.scale.setScalar(Math.max(0.0001, piece.scale));
            mesh.visible = piece.scale > 0.01;

            // The mated king goes over.
            const falling = piece === state.mated && state.clock > state.resetAt - 4.6 ? 1 : 0;
            piece.fallen += (falling - piece.fallen) * Math.min(1, delta * 3.2);
            mesh.rotation.z = -piece.fallen * 1.48;
            mesh.position.y += piece.fallen * 0.26;
        }

        renderer.render(scene, camera);
    }

    let stopped = false;
    const stopLoop = runLoop(canvas, frame, () => (low ? LOW_FPS : 0));
    canvas.addEventListener('webglcontextlost', () => !stopped && options.onFail?.());

    // If perf.js finds the page too slow while the board is running, the
    // board drops to the low settings where it stands. Antialiasing and the
    // shape of the pieces are fixed when the scene is made, so those two stay.
    const stopWatching = tier()?.onDemote(() => {
        low = true;
        renderer.setPixelRatio(1);
        renderer.shadowMap.enabled = false;
        keyLight.castShadow = false;
        scene.remove(cursorLight);
        scene.traverse((object) => {
            if (object.material) object.material.needsUpdate = true;
        });
    });

    function destroy() {
        if (stopped) return;
        stopped = true;
        stopLoop();
        stopFit();
        stopWatching?.();
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerdown', onDown);
        window.removeEventListener('scroll', onScroll);
        document.removeEventListener('checkora:theme', paintForTheme);
        renderer.dispose();
    }
    function giveUp() {
        destroy();
        renderer.forceContextLoss();
        options.onFail?.();
    }

    return { destroy };
}

/**
 * One piece turning slowly on a small plinth. It leans toward the pointer.
 * options.type is one of p, n, b, r, q, k; options.color is 'w' (ivory) or 'b'.
 * options.fallen lays the piece on its side, for the error pages.
 */
export function mountPiece(canvas, options = {}) {
    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const renderer = createRenderer(canvas);
    const scene = new THREE.Scene();
    lightScene(scene, renderer);

    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 50);
    camera.position.set(0, 1.5, 5.2);
    camera.lookAt(0, 0.62, 0);
    const stopFit = fit(renderer, camera, canvas);

    const group = new THREE.Group();
    const piece = new THREE.Mesh(buildGeometry()[options.type || 'k'], buildMaterials()[options.color || 'w']);
    piece.castShadow = true;
    piece.scale.setScalar(1.25);
    if (options.fallen) {
        piece.rotation.z = -1.48;
        piece.position.set(-0.55, 0.45, 0);
    }
    group.add(piece);

    const plinth = new THREE.Mesh(
        new THREE.CylinderGeometry(0.9, 0.98, 0.14, 64),
        new THREE.MeshPhysicalMaterial({ color: 0x0e0e12, metalness: 0.7, roughness: 0.22, clearcoat: 1 }),
    );
    plinth.position.y = -0.07;
    plinth.receiveShadow = true;
    group.add(plinth);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.94, 0.012, 12, 96), new THREE.MeshStandardMaterial({ color: 0xf0b13a, metalness: 1, roughness: 0.25 }));
    ring.rotation.x = Math.PI / 2;
    group.add(ring);
    scene.add(group);

    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
    function onMove(event) {
        pointer.tx = (event.clientX / window.innerWidth) * 2 - 1;
        pointer.ty = (event.clientY / window.innerHeight) * 2 - 1;
    }
    window.addEventListener('pointermove', onMove, { passive: true });

    let turn = 0.5;
    const stopLoop = runLoop(canvas, (delta) => {
        if (!calm) turn += delta * 0.45;
        pointer.x += (pointer.tx - pointer.x) * Math.min(1, delta * 4);
        pointer.y += (pointer.ty - pointer.y) * Math.min(1, delta * 4);
        group.rotation.y = turn + pointer.x * 0.5;
        group.rotation.x = pointer.y * 0.12;
        renderer.render(scene, camera);
    });

    let stopped = false;
    const destroy = () => {
        if (stopped) return;
        stopped = true;
        stopLoop();
        stopFit();
        stopWatching?.();
        window.removeEventListener('pointermove', onMove);
        renderer.dispose();
    };
    canvas.addEventListener('webglcontextlost', () => !stopped && options.onFail?.());

    // The low tier has no single pieces. If perf.js moves this page down
    // while one is turning, it stops, gives its WebGL context back, and
    // onFail puts the page's flat piece in its place.
    const stopWatching = tier()?.onDemote(() => {
        destroy();
        renderer.forceContextLoss();
        options.onFail?.();
    });

    return { destroy };
}

export function canRender3D() {
    try {
        const probe = document.createElement('canvas');
        return Boolean(probe.getContext('webgl2') || probe.getContext('webgl'));
    } catch (error) {
        return false;
    }
}

/**
 * Should this page mount a 3D scene? Every page asks here before it mounts
 * one, so the rule is kept in one place: perf.js says what the machine's tier
 * allows, and the browser has to have WebGL.
 * kind is 'hero' for the landing board or 'piece' for a single piece.
 * A page that loads this file lazily can ask window.checkoraPerf.wants3D(kind)
 * first and skip the download when the answer is no.
 */
export function shouldMount3D(kind = 'piece') {
    const perf = tier();
    if (perf && !perf.wants3D(kind)) return false;
    return canRender3D();
}
