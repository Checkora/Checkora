// Makes the wood for the default ("gilded") board: maple for the light
// squares, walnut for the dark ones, and the walnut frame round the board.
//
// Everything is drawn from noise in a Chrome canvas, so there is nothing to
// download and the result is the same each time (the noise is seeded). Each
// square texture holds the wood twice, side by side: as drawn, and turned
// half round. play.css shows a turned board from the second copy, so a
// square keeps its own grain when the board is flipped.
//
//   PLAYWRIGHT=/path/to/node_modules/playwright node scripts/render_wood.mjs
//
// Playwright is not a dependency of the project; point PLAYWRIGHT at any copy
// of it. Writes game/static/game/board/{maple,walnut,frame}.webp, or to
// --out <dir>. --quality sets the WebP quality (0.8).

import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const args = process.argv.slice(2);
const option = (name, fallback) => {
    const at = args.indexOf(`--${name}`);
    return at >= 0 && args[at + 1] ? args[at + 1] : fallback;
};
const root = fileURLToPath(new URL('..', import.meta.url));
const out = option('out', join(root, 'game/static/game/board'));
const quality = Number(option('quality', 0.8));

const playwright = await import(process.env.PLAYWRIGHT || 'playwright');
const { chromium } = playwright.chromium ? playwright : playwright.default;

// Runs in the page. Returns data URLs.
function draw({ quality }) {
    // Seeded value noise, so the wood comes out the same on every run.
    function noise(seed) {
        let s = seed >>> 0;
        const random = () => {
            s = (s + 0x6d2b79f5) >>> 0;
            let t = s;
            t = Math.imul(t ^ (t >>> 15), t | 1);
            t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
        const values = new Float32Array(256).map(() => random());
        const perm = new Uint8Array(512);
        const order = Array.from({ length: 256 }, (_, i) => i);
        for (let i = 255; i > 0; i--) {
            const j = Math.floor(random() * (i + 1));
            [order[i], order[j]] = [order[j], order[i]];
        }
        for (let i = 0; i < 512; i++) perm[i] = order[i & 255];
        const at = (x, y) => values[perm[(perm[x & 255] + y) & 255]];
        const smooth = (t) => t * t * (3 - 2 * t);
        const value = (x, y) => {
            const xi = Math.floor(x);
            const yi = Math.floor(y);
            const fx = smooth(x - xi);
            const fy = smooth(y - yi);
            const a = at(xi, yi) + (at(xi + 1, yi) - at(xi, yi)) * fx;
            const b = at(xi, yi + 1) + (at(xi + 1, yi + 1) - at(xi, yi + 1)) * fx;
            return a + (b - a) * fy;
        };
        value.fbm = (x, y, octaves = 5) => {
            let sum = 0;
            let amp = 0.5;
            let norm = 0;
            for (let i = 0; i < octaves; i++) {
                sum += value(x, y) * amp;
                norm += amp;
                x *= 2.03;
                y *= 2.03;
                amp *= 0.5;
            }
            return sum / norm;
        };
        return value;
    }

    const mix = (a, b, t) => a + (b - a) * t;
    const step = (a, b, x) => {
        const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
        return t * t * (3 - 2 * t);
    };
    const hex = (h) => [(h >> 16) & 255, (h >> 8) & 255, h & 255];

    // A wood is a function from a point (u across the grain, v along it, both
    // in tile widths) to a colour. Growth rings run along v and wander.
    function wood({ seed, light, dark, deep, rings, contrast, streaks, pores, curl, wander = 1 }) {
        const n = noise(seed);
        const m = noise(seed + 101);
        const p = noise(seed + 202);
        const L = hex(light);
        const D = hex(dark);
        const K = hex(deep);
        return (u, v) => {
            const warp = (n.fbm(u * 2.2, v * 0.35, 5) * 1.6 + m.fbm(u * 9, v * 1.4, 3) * 0.18) * wander;
            const r = u * rings + warp * 2.4;
            const ring = r - Math.floor(r);
            // Late wood: a narrow darker band at the end of each year.
            const late = step(0.58, 0.9, ring) * (1 - step(0.9, 1, ring));
            const tone = n.fbm(u * 1.3 + 7, v * 0.8, 4);
            const streak = m.fbm(u * 46 + warp * 4, v * 1.6, 3);
            let t = 0.35 + (tone - 0.5) * 1.1 + late * contrast + (streak - 0.5) * streaks;
            // Pores: short dark dashes along the grain.
            const pore = p(u * 520, v * 26);
            t += step(0.8, 0.95, pore) * pores;
            // Curly figure: faint bands across the grain.
            let shine = 0;
            if (curl) shine = Math.sin(v * 70 + n.fbm(u * 3, v * 3, 3) * 9) * curl * (0.6 + 0.4 * tone);
            t = Math.min(1.15, Math.max(-0.1, t));
            const c = t < 0.7 ? [0, 1, 2].map((i) => mix(L[i], D[i], t / 0.7)) : [0, 1, 2].map((i) => mix(D[i], K[i], (t - 0.7) / 0.45));
            return c.map((x) => x * (1 + shine));
        };
    }

    const maple = wood({ seed: 11, light: 0xf0dbb0, dark: 0xdcbd88, deep: 0xbf955f, rings: 9, contrast: 0.32, streaks: 0.16, pores: 0.03, curl: 0.012, wander: 0.55 });
    const walnut = wood({ seed: 29, light: 0x87593a, dark: 0x5e3b24, deep: 0x351f12, rings: 10, contrast: 0.45, streaks: 0.42, pores: 0.22, curl: 0, wander: 0.8 });

    // One tile of wood, then the same tile turned half round beside it.
    function tile(paint, size) {
        const canvas = document.createElement('canvas');
        canvas.width = size * 2;
        canvas.height = size;
        const ctx = canvas.getContext('2d');
        const image = ctx.createImageData(size, size);
        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const [r, g, b] = paint(x / size, y / size);
                const i = (y * size + x) * 4;
                image.data[i] = r;
                image.data[i + 1] = g;
                image.data[i + 2] = b;
                image.data[i + 3] = 255;
            }
        }
        ctx.putImageData(image, 0, 0);
        ctx.save();
        ctx.translate(size * 2, size);
        ctx.rotate(Math.PI);
        ctx.drawImage(canvas, 0, 0, size, size, 0, 0, size, size);
        ctx.restore();
        return canvas;
    }

    // The frame: four walnut rails mitred at the corners, the grain running
    // along each rail. Across a rail, from the outside in: a rounded outer
    // edge, the flat top, a chamfer down towards the squares, and a thin
    // maple stringing line where the frame meets the board. The light falls
    // from straight above, so the frame looks the same turned round.
    function frame(size, band) {
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = size;
        const ctx = canvas.getContext('2d');
        const image = ctx.createImageData(size, size);
        const grain = wood({ seed: 47, light: 0x80553a, dark: 0x553520, deep: 0x2a170c, rings: 7, contrast: 0.5, streaks: 0.45, pores: 0.22, curl: 0 });
        const line = hex(0xe9d3a4);
        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const i = (y * size + x) * 4;
                // Distance in from each side; the nearest side owns the pixel.
                const sides = [y, size - 1 - y, x, size - 1 - x];
                let side = 0;
                for (let k = 1; k < 4; k++) if (sides[k] < sides[side]) side = k;
                const across = sides[side];
                if (across >= band) {
                    image.data[i + 3] = 0;
                    continue;
                }
                const along = side < 2 ? x : y;
                const a = across / band;
                // Each rail is cut from a different part of the plank.
                let [r, g, b] = grain(a * 0.22 + side * 0.31, along / size * 0.9 + side * 0.17);
                let light = 1;
                if (a < 0.1) light = 0.62 + 0.55 * Math.sin((a / 0.1) * Math.PI * 0.5);
                else if (a < 0.16) light = 1.17 - (a - 0.1) * 2.5;
                else if (a < 0.68) light = 1.02 - (a - 0.16) * 0.12;
                else if (a < 0.7) light = 1.22;
                else if (a < 0.88) light = 0.84 - (a - 0.7) * 0.9;
                else if (a < 0.9) light = 0.5;
                if (a >= 0.9 && a < 0.955) {
                    [r, g, b] = line.map((c) => c * (0.9 + 0.12 * Math.sin(((a - 0.9) / 0.055) * Math.PI)));
                    light = 1;
                } else if (a >= 0.955) {
                    light = 0.35;
                }
                // The mitre joint shows as a hairline.
                const second = [...sides].sort((p, q) => p - q)[1];
                if (second - across < 1.2 && a < 0.9) light *= 0.72;
                image.data[i] = Math.min(255, r * light);
                image.data[i + 1] = Math.min(255, g * light);
                image.data[i + 2] = Math.min(255, b * light);
                image.data[i + 3] = 255;
            }
        }
        ctx.putImageData(image, 0, 0);
        return canvas;
    }

    return {
        maple: tile(maple, 640).toDataURL('image/webp', quality),
        walnut: tile(walnut, 640).toDataURL('image/webp', quality),
        frame: frame(640, 96).toDataURL('image/webp', quality + 0.08),
    };
}

const browser = await chromium.launch({ channel: 'chrome' });
try {
    const page = await browser.newPage();
    await page.setContent('<!doctype html><title>wood</title>');
    const files = await page.evaluate(draw, { quality });
    await mkdir(out, { recursive: true });
    for (const [name, url] of Object.entries(files)) {
        if (!url.startsWith('data:image/webp')) throw new Error('This Chrome cannot write WebP.');
        const bytes = Buffer.from(url.split(',')[1], 'base64');
        await writeFile(join(out, `${name}.webp`), bytes);
        console.log(`${name}.webp ${(bytes.length / 1024).toFixed(1)} KB`);
    }
} finally {
    await browser.close();
}
