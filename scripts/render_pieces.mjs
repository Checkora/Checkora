// Renders the "staunton" piece set used on the flat boards.
//
// The pieces are the three.js models in game/static/game/js/scene3d.js (the
// same ones the landing page turns), photographed one at a time in Chrome
// from a little above the board, under a soft key light with a rim light
// behind and a soft shadow where the piece stands. Knights face left for
// both colours, as in printed diagrams. The result is twelve WebP files with
// transparency in game/static/game/pieces/staunton/, all framed alike so a
// king stands taller than a pawn, for boards.
//
// With --single the same pieces are framed one by one, each filling its
// picture, with only the shadow right under the foot. Those go in
// pieces/staunton-single/ and are for a piece shown on its own: icons, the
// pieces taken in a game, the promotion choice, the stand-ins for the
// turning 3D pieces.
//
//   PLAYWRIGHT=/path/to/node_modules/playwright node scripts/render_pieces.mjs
//
// Playwright is not a dependency of the project; point PLAYWRIGHT at any copy
// of it (or run from a folder where `import('playwright')` resolves). Google
// Chrome has to be installed. Options:
//   --size 256        width and height of each image, in pixels
//   --quality 0.86    WebP quality
//   --out <dir>       write somewhere else (to compare with the current set)
//   --sheet <file>    also write a PNG with every piece on light and dark squares
//   --single          the set framed piece by piece (192 px)
//
// Run it again after changing a model in scene3d.js.

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const args = process.argv.slice(2);
const option = (name, fallback) => {
    const at = args.indexOf(`--${name}`);
    return at >= 0 && args[at + 1] && !args[at + 1].startsWith('--') ? args[at + 1] : fallback;
};
const single = args.includes('--single');
const root = fileURLToPath(new URL('..', import.meta.url));
const statics = join(root, 'game/static/game');
const size = Number(option('size', single ? 192 : 256));
const quality = Number(option('quality', 0.86));
const out = option('out', join(statics, single ? 'pieces/staunton-single' : 'pieces/staunton'));
const sheet = option('sheet', '');

const playwright = await import(process.env.PLAYWRIGHT || 'playwright');
const { chromium } = playwright.chromium ? playwright : playwright.default;

const ORIGIN = 'http://pieces.render';
const TYPES = { '.js': 'text/javascript', '.html': 'text/html' };

// The page that does the work. It imports three.js and the models from the
// repository, so what it renders is exactly what the site ships.
const PAGE = `<!doctype html>
<meta charset="utf-8">
<script type="importmap">{ "imports": { "three": "/vendor/three/three.module.min.js" } }</script>
<script type="module">
import * as THREE from 'three';
import { RoomEnvironment } from '/vendor/three/RoomEnvironment.js';
import { buildGeometry, buildMaterials } from '/js/scene3d.js';

// Radius of each piece's foot, for the shadow right under it.
const FOOT = { p: 0.3, r: 0.32, b: 0.31, q: 0.33, k: 0.34, n: 0.33 };

window.renderSet = async ({ size, single }) => {
    const scale = 4;
    const full = size * scale;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = full;
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1);
    renderer.setSize(full, full, false);
    renderer.setClearColor(0x000000, 0);
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.VSMShadowMap;

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.42;

    // A large soft key from the front left, a warm rim from behind on the
    // right, a cool one from behind on the left and a little fill.
    const key = new THREE.DirectionalLight(0xfff2e0, 2.5);
    key.position.set(-3, 7.6, 4.2);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.radius = 14;
    key.shadow.blurSamples = 24;
    key.shadow.bias = -0.0006;
    Object.assign(key.shadow.camera, { left: -1.4, right: 1.4, top: 1.6, bottom: -1.4, near: 1, far: 20 });
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xffe2b8, 2.6);
    rim.position.set(3.6, 3.4, -4.6);
    scene.add(rim);
    const cool = new THREE.DirectionalLight(0xdce6ff, 1.1);
    cool.position.set(-4.4, 2.6, -3.6);
    scene.add(cool);
    const fill = new THREE.DirectionalLight(0xffffff, 0.45);
    fill.position.set(4.2, 1.2, 4.6);
    scene.add(fill);

    // The shadow the key light casts, and a darker one right under the foot
    // where no light reaches at all.
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(8, 8), new THREE.ShadowMaterial({ opacity: single ? 0 : 0.24 }));
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);
    const blob = document.createElement('canvas');
    blob.width = blob.height = 256;
    const g = blob.getContext('2d');
    const grad = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    grad.addColorStop(0, 'rgba(0,0,0,0.85)');
    grad.addColorStop(0.42, 'rgba(0,0,0,0.6)');
    grad.addColorStop(0.62, 'rgba(0,0,0,0.22)');
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = grad;
    g.fillRect(0, 0, 256, 256);
    const contact = new THREE.Mesh(
        new THREE.PlaneGeometry(1, 1),
        new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(blob), color: 0x000000, transparent: true, depthWrite: false, opacity: 0.7 }),
    );
    contact.rotation.x = -Math.PI / 2;
    contact.position.y = 0.001;
    contact.renderOrder = -1;
    scene.add(contact);

    // A long lens from 20 degrees above the board. Every piece is framed the
    // same, so a king is taller than a pawn here as it is on a real board.
    const elevation = (20 * Math.PI) / 180;
    const distance = 9;
    const half = 0.71;
    const target = new THREE.Vector3(0, 0.6, 0);
    const camera = new THREE.PerspectiveCamera((2 * Math.atan(half / distance) * 180) / Math.PI, 1, 0.1, 40);
    camera.position.set(0, target.y + Math.sin(elevation) * distance, Math.cos(elevation) * distance);
    camera.lookAt(target);

    const geometry = buildGeometry(160, 0.0032);
    const materials = buildMaterials();
    const images = {};
    for (const colour of ['w', 'b']) {
        for (const type of ['k', 'q', 'r', 'b', 'n', 'p']) {
            const mesh = new THREE.Mesh(geometry[type], materials[colour]);
            mesh.castShadow = true;
            // The knight turns a little towards the camera, so its face shows.
            if (type === 'n') mesh.rotation.y = 0.5;
            scene.add(mesh);
            const foot = FOOT[type] * 2.7;
            contact.scale.set(foot, foot, 1);
            renderer.render(scene, camera);
            scene.remove(mesh);

            // A single piece is cut out of the frame round its own outline:
            // as tall as it is, centred, standing near the bottom.
            let source = canvas;
            let width = full;
            if (single) {
                source = cropToPiece(canvas, full);
                width = source.width;
            }

            // Down to the final size a half at a time, which keeps edges clean.
            while (width > size) {
                width = Math.max(size, width / 2);
                const step = document.createElement('canvas');
                step.width = step.height = width;
                const ctx = step.getContext('2d');
                ctx.imageSmoothingQuality = 'high';
                ctx.drawImage(source, 0, 0, width, width);
                source = step;
            }
            images[colour + type] = source;
        }
    }
    return images;
};

// The square round a piece: its height plus a margin, centred on it, with
// the foot (and the shadow under it) near the bottom edge.
function cropToPiece(canvas, full) {
    const probe = document.createElement('canvas');
    probe.width = probe.height = full;
    const ctx = probe.getContext('2d');
    ctx.drawImage(canvas, 0, 0);
    const { data } = ctx.getImageData(0, 0, full, full);
    let top = full;
    let bottom = 0;
    let left = full;
    let right = 0;
    for (let y = 0; y < full; y++) {
        for (let x = 0; x < full; x++) {
            // The body only: the soft shadow never gets this opaque.
            if (data[(y * full + x) * 4 + 3] < 230) continue;
            if (y < top) top = y;
            if (y > bottom) bottom = y;
            if (x < left) left = x;
            if (x > right) right = x;
        }
    }
    const side = Math.round(Math.max(bottom - top, right - left) * 1.1);
    const cx = (left + right) / 2;
    const cut = document.createElement('canvas');
    cut.width = cut.height = side;
    cut.getContext('2d').drawImage(canvas, cx - side / 2, bottom + side * 0.045 - side, side, side, 0, 0, side, side);
    return cut;
}

window.encode = async ({ size, quality, sheet, single }) => {
    const images = await window.renderSet({ size, single });
    const files = {};
    for (const [name, image] of Object.entries(images)) files[name] = image.toDataURL('image/webp', quality);
    if (sheet) {
        // Every piece on a light and a dark square, to look at the set.
        const cell = size;
        const page = document.createElement('canvas');
        page.width = cell * 6;
        page.height = cell * 4;
        const ctx = page.getContext('2d');
        const names = Object.keys(images);
        names.forEach((name, i) => {
            for (const row of [0, 1]) {
                const x = (i % 6) * cell;
                const y = (Math.floor(i / 6) * 2 + row) * cell;
                ctx.fillStyle = (i + row) % 2 ? '#5b3a24' : '#e6cfa3';
                ctx.fillRect(x, y, cell, cell);
                ctx.drawImage(images[name], x, y, cell, cell);
            }
        });
        files.sheet = page.toDataURL('image/png');
    }
    return files;
};
window.ready = true;
</script>`;

const browser = await chromium.launch({
    channel: 'chrome',
    args: ['--enable-gpu', ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])],
});
try {
    const page = await browser.newPage();
    page.on('pageerror', (error) => console.error('page error:', error.message));
    page.on('console', (message) => message.type() === 'error' && console.error('page:', message.text()));
    await page.route(`${ORIGIN}/**`, async (route) => {
        const path = new URL(route.request().url()).pathname;
        if (path === '/') return route.fulfill({ body: PAGE, contentType: 'text/html' });
        try {
            const body = await readFile(join(statics, path));
            return route.fulfill({ body, contentType: TYPES[extname(path)] || 'application/octet-stream' });
        } catch {
            return route.fulfill({ status: 404, body: '' });
        }
    });
    await page.goto(`${ORIGIN}/`);
    await page.waitForFunction(() => window.ready === true);
    const files = await page.evaluate((options) => window.encode(options), { size, quality, sheet: Boolean(sheet), single });

    await mkdir(out, { recursive: true });
    let total = 0;
    for (const [name, url] of Object.entries(files)) {
        const bytes = Buffer.from(url.split(',')[1], 'base64');
        if (name === 'sheet') {
            await writeFile(sheet, bytes);
            continue;
        }
        if (!url.startsWith('data:image/webp')) throw new Error('This Chrome cannot write WebP.');
        await writeFile(join(out, `${name}.webp`), bytes);
        total += bytes.length;
    }
    console.log(`${Object.keys(files).filter((name) => name !== 'sheet').length} pieces, ${(total / 1024).toFixed(1)} KB, in ${out}`);
} finally {
    await browser.close();
}
