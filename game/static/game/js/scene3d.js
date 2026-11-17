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

/* ---------- the chess set ----------
   Each piece is turned on a lathe from a half outline, as a wooden Staunton
   set is, and the carved parts are added to it: the rook's battlements, the
   cut in the bishop's mitre, the queen's coronet, the king's cross and the
   knight's head. Units are board squares and every piece stands on y = 0.
   The knight looks along -x. scripts/render_pieces.mjs photographs these
   same models for the flat boards, so a change here shows up there too once
   the set is rendered again. */

const v2 = (x, y) => new THREE.Vector2(x, y);
const ramp = (a, b, x) => {
    const t = clamp01((x - a) / (b - a));
    return t * t * (3 - 2 * t);
};
const bump = (dx, dy, r) => Math.exp(-(dx * dx + dy * dy) / (r * r));

// A half outline written as pen moves, from the axis at the foot to the axis
// at the top: ['L', x, y] a straight line, ['Q', cx, cy, x, y] and
// ['C', ax, ay, bx, by, x, y] curves, ['A', cx, cy, r, from, to] an arc in
// degrees that starts where the pen is. A last value of true leaves a crisp
// edge at the end of the move; everywhere else the turning is smooth.
function outline(moves, detail) {
    const points = [v2(moves[0][0], moves[0][1])];
    for (const [kind, ...a] of moves.slice(1)) {
        const from = points[points.length - 1];
        let sharp = false;
        if (kind === 'A') {
            const [cx, cy, r, start, end] = a;
            const steps = Math.max(3, Math.round((detail * Math.abs(end - start)) / 60));
            for (let i = 1; i <= steps; i++) {
                const t = ((start + ((end - start) * i) / steps) * Math.PI) / 180;
                points.push(v2(cx + r * Math.cos(t), cy + r * Math.sin(t)));
            }
            sharp = a[5];
        } else {
            let curve;
            if (kind === 'L') curve = new THREE.LineCurve(from, v2(a[0], a[1]));
            else if (kind === 'Q') curve = new THREE.QuadraticBezierCurve(from, v2(a[0], a[1]), v2(a[2], a[3]));
            else curve = new THREE.CubicBezierCurve(from, v2(a[0], a[1]), v2(a[2], a[3]), v2(a[4], a[5]));
            // A curve may ask for more points than the rest of the outline.
            const steps = kind === 'L' ? 1 : a[kind === 'Q' ? 5 : 7] || detail;
            for (let i = 1; i <= steps; i++) points.push(curve.getPoint(i / steps));
            sharp = a[kind === 'L' ? 2 : kind === 'Q' ? 4 : 6];
        }
        // A point given twice splits the normals, so the edge stays crisp.
        if (sharp) points.push(points[points.length - 1].clone());
    }
    points.forEach((point) => {
        point.x = Math.max(0, point.x);
    });
    return points;
}

// The lathe's seam is put at the back, and its two copies of each point are
// given one normal between them so the seam does not show.
function lathe(points, segments) {
    const geometry = new THREE.LatheGeometry(points, segments, Math.PI, Math.PI * 2);
    return geometry;
}
function mendSeam(geometry, segments, rows) {
    const normal = geometry.attributes.normal;
    const a = new THREE.Vector3();
    const b = new THREE.Vector3();
    for (let j = 0; j < rows; j++) {
        a.fromBufferAttribute(normal, j);
        b.fromBufferAttribute(normal, segments * rows + j);
        a.add(b).normalize();
        normal.setXYZ(j, a.x, a.y, a.z);
        normal.setXYZ(segments * rows + j, a.x, a.y, a.z);
    }
    normal.needsUpdate = true;
}

// Every part carries a colour per vertex, used as shade: 1 is the bare
// wood, less is a hollow the light reaches less (the bishop's cut, the
// knight's eye and nostril, the grooves of the mane).
function shaded(geometry, shade = () => 1) {
    const position = geometry.attributes.position;
    const colour = new Float32Array(position.count * 3);
    for (let i = 0; i < position.count; i++) {
        const s = shade(position.getX(i), position.getY(i), position.getZ(i));
        colour[i * 3] = colour[i * 3 + 1] = colour[i * 3 + 2] = s;
    }
    geometry.setAttribute('color', new THREE.BufferAttribute(colour, 3));
    return geometry;
}

// Joins parts into one geometry (positions, normals and shade).
function join(parts) {
    const flat = parts.map((part) => {
        if (!part.attributes.normal) part.computeVertexNormals();
        if (!part.attributes.color) shaded(part);
        return part.index ? part.toNonIndexed() : part;
    });
    const size = flat.reduce((sum, part) => sum + part.attributes.position.count, 0);
    const merged = new THREE.BufferGeometry();
    for (const name of ['position', 'normal', 'color']) {
        const array = new Float32Array(size * 3);
        let offset = 0;
        for (const part of flat) {
            array.set(part.attributes[name].array, offset);
            offset += part.attributes[name].count * 3;
        }
        merged.setAttribute(name, new THREE.BufferAttribute(array, 3));
    }
    merged.computeBoundingSphere();
    return merged;
}

// The foot every piece shares: a flat plinth, a rounded bead, a cove and a
// second, smaller bead, ending where the stem starts at (stemX, stemY).
function foot(radius, stemX, stemY) {
    const r = radius;
    return [
        [0, 0],
        ['L', r - 0.012, 0],
        ['Q', r + 0.004, 0.002, r + 0.002, 0.03],
        ['Q', r + 0.002, 0.07, r - 0.035, 0.078, true],
        ['L', r - 0.045, 0.092],
        ['Q', r - 0.09, 0.098, r - 0.1, 0.118],
        ['Q', r - 0.085, 0.13, r - 0.098, 0.146],
        ['Q', stemX + 0.02, stemY - 0.02, stemX, stemY],
    ];
}

function pawnOutline(detail) {
    return outline([
        ...foot(0.3, 0.13, 0.2),
        ['Q', 0.098, 0.3, 0.092, 0.39],
        ['Q', 0.17, 0.392, 0.182, 0.41],
        ['Q', 0.188, 0.428, 0.17, 0.44, true],
        ['Q', 0.115, 0.45, 0.083, 0.468],
        ['A', 0, 0.598, 0.152, -58.6, 90],
    ], detail);
}

function rookOutline(detail) {
    return outline([
        ...foot(0.32, 0.215, 0.18),
        ['Q', 0.17, 0.36, 0.185, 0.52],
        ['Q', 0.235, 0.528, 0.24, 0.548],
        ['Q', 0.242, 0.57, 0.215, 0.575, true],
        ['Q', 0.225, 0.6, 0.252, 0.64],
        ['L', 0.252, 0.7, true],
        ['L', 0.19, 0.7, true],
        ['L', 0.19, 0.668, true],
        ['L', 0, 0.668],
    ], detail);
}

function bishopOutline(detail) {
    return outline([
        ...foot(0.31, 0.15, 0.19),
        ['Q', 0.1, 0.36, 0.088, 0.53],
        ['Q', 0.16, 0.532, 0.172, 0.552],
        ['Q', 0.178, 0.572, 0.15, 0.58, true],
        ['Q', 0.135, 0.592, 0.142, 0.605],
        ['Q', 0.146, 0.622, 0.11, 0.628, true],
        ['Q', 0.085, 0.634, 0.09, 0.65],
        // The mitre is turned finely: the cut across it needs the points.
        ['C', 0.19, 0.7, 0.175, 0.86, 0.06, 0.94, false, detail * 6],
        ['Q', 0.03, 0.958, 0.034, 0.966],
        ['A', 0, 0.998, 0.04, -53, 90],
    ], detail);
}

function queenOutline(detail) {
    return outline([
        ...foot(0.33, 0.165, 0.2),
        ['Q', 0.105, 0.42, 0.098, 0.62],
        ['Q', 0.185, 0.622, 0.196, 0.642],
        ['Q', 0.2, 0.664, 0.17, 0.67, true],
        ['Q', 0.125, 0.676, 0.13, 0.69],
        ['Q', 0.134, 0.705, 0.1, 0.71, true],
        ['Q', 0.098, 0.8, 0.15, 0.88],
        ['Q', 0.185, 0.93, 0.205, 0.975],
        ['Q', 0.208, 0.99, 0.196, 0.992, true],
        ['Q', 0.15, 0.97, 0.11, 0.975],
        ['Q', 0.06, 0.985, 0.05, 1.03],
        ['Q', 0.04, 1.045, 0.03, 1.05],
        ['A', 0, 1.085, 0.046, -50, 90],
    ], detail);
}

function kingOutline(detail) {
    return outline([
        ...foot(0.34, 0.175, 0.2),
        ['Q', 0.11, 0.45, 0.104, 0.66],
        ['Q', 0.195, 0.662, 0.205, 0.684],
        ['Q', 0.208, 0.706, 0.178, 0.712, true],
        ['Q', 0.13, 0.718, 0.136, 0.732],
        ['Q', 0.14, 0.748, 0.104, 0.754, true],
        ['Q', 0.1, 0.86, 0.165, 0.95],
        ['Q', 0.198, 0.99, 0.2, 1.02],
        ['Q', 0.2, 1.036, 0.186, 1.04, true],
        ['Q', 0.17, 1.045, 0.14, 1.05],
        ['Q', 0.1, 1.06, 0.075, 1.1],
        ['Q', 0.06, 1.12, 0.03, 1.122, true],
        ['L', 0, 1.122],
    ], detail);
}

function knightFoot(detail) {
    return outline([
        ...foot(0.33, 0.24, 0.165),
        ['Q', 0.235, 0.18, 0.2, 0.19, true],
        ['L', 0, 0.19],
    ], detail);
}

// The knight's head, drawn as its side view. The outline is inflated into a
// rounded solid, thick at the neck and thin at the muzzle, and then carved:
// eye, nostril, mouth, the line of the jaw and the strands of the mane.
const KNIGHT_SIDE = [
    [0.205, 0.13], [0.225, 0.22], [0.232, 0.31], [0.226, 0.4], [0.208, 0.49], [0.18, 0.575], [0.145, 0.65],
    [0.108, 0.715], [0.07, 0.775], [0.04, 0.83], [0.022, 0.868], [-0.004, 0.892], [-0.045, 0.896],
    [-0.09, 0.884], [-0.14, 0.858], [-0.195, 0.818], [-0.25, 0.765], [-0.296, 0.708], [-0.334, 0.652],
    [-0.36, 0.605], [-0.368, 0.572], [-0.36, 0.548], [-0.335, 0.536], [-0.318, 0.532], [-0.334, 0.518],
    [-0.33, 0.5], [-0.3, 0.488], [-0.25, 0.49], [-0.19, 0.505], [-0.13, 0.528], [-0.075, 0.548],
    [-0.05, 0.52], [-0.06, 0.47], [-0.085, 0.41], [-0.12, 0.35], [-0.16, 0.29], [-0.19, 0.22], [-0.195, 0.13],
];
// Where the mane runs: the stretch of the outline from the withers to the poll.
const MANE = { from: 1, to: 10 };

function knightSilhouette(samples) {
    const curve = new THREE.CatmullRomCurve3(KNIGHT_SIDE.map(([x, y]) => new THREE.Vector3(x, y, 0)), true, 'centripetal');
    return curve.getSpacedPoints(samples).slice(0, -1).map((p) => [p.x, p.y]);
}

function knightHead(cell) {
    const ring = knightSilhouette(Math.round(1.6 / cell));
    const count = ring.length;
    // Arc length at each outline point, for the mane's strands.
    const along = [0];
    for (let i = 1; i < count; i++) along.push(along[i - 1] + Math.hypot(ring[i][0] - ring[i - 1][0], ring[i][1] - ring[i - 1][1]));
    const maneFrom = Math.round((MANE.from / KNIGHT_SIDE.length) * count);
    const maneTo = Math.round((MANE.to / KNIGHT_SIDE.length) * count);

    // Signed distance to the outline (positive inside) and the nearest point.
    function probe(x, y) {
        let best = Infinity;
        let nearest = 0;
        let inside = false;
        for (let i = 0, j = count - 1; i < count; j = i++) {
            const [ax, ay] = ring[j];
            const [bx, by] = ring[i];
            if ((ay > y) !== (by > y) && x < ((bx - ax) * (y - ay)) / (by - ay) + ax) inside = !inside;
            const ex = bx - ax;
            const ey = by - ay;
            const t = clamp01(((x - ax) * ex + (y - ay) * ey) / (ex * ex + ey * ey));
            const dx = x - (ax + ex * t);
            const dy = y - (ay + ey * t);
            const d = dx * dx + dy * dy;
            if (d < best) {
                best = d;
                nearest = t < 0.5 ? j : i;
            }
        }
        const d = Math.sqrt(best);
        return { d: inside ? d : -d, nearest };
    }

    // How far the surface stands out from the middle plane, and its shade.
    function carve(x, y, d, nearest) {
        // Thickness: a full neck, a rounder jowl, a narrow muzzle and brow.
        let half = 0.118;
        half *= 1 - 0.42 * ramp(-0.1, -0.36, x) * ramp(0.46, 0.6, y);
        half *= 1 - 0.22 * ramp(0.76, 0.9, y);
        half += 0.022 * bump(x + 0.01, y - 0.63, 0.085);
        half += 0.012 * bump(x - 0.06, y - 0.3, 0.12);
        let z = half * Math.sqrt(1 - Math.exp(-d / 0.045));
        let shade = 1;

        // The eye: a rounded ball in a socket, under a brow.
        const ex = x + 0.098;
        const ey = y - 0.792;
        const er = Math.hypot(ex * 1.15, ey);
        z += 0.009 * bump(ex * 1.15, ey, 0.016) - 0.006 * Math.exp(-((er - 0.026) ** 2) / 0.00007);
        z += 0.007 * bump(x + 0.075, y - 0.83, 0.03);
        shade -= 0.45 * Math.exp(-((er - 0.022) ** 2) / 0.00005);

        // The nostril and the line of the mouth.
        z -= 0.013 * bump(x + 0.322, y - 0.6, 0.016);
        shade -= 0.5 * bump(x + 0.322, y - 0.6, 0.013);
        const mouth = Math.abs(y - (0.532 + (x + 0.318) * 0.12));
        const onMouth = ramp(-0.21, -0.25, x) * ramp(-0.37, -0.33, x);
        z -= 0.008 * onMouth * Math.exp(-(mouth * mouth) / 0.00004);
        shade -= 0.4 * onMouth * Math.exp(-(mouth * mouth) / 0.00003);

        // The edge of the jaw, a shallow crease round the jowl.
        const jaw = Math.hypot(x + 0.01, y - 0.63) - 0.1;
        const onJaw = ramp(0.5, 0.56, y) * ramp(0.1, 0.02, x);
        z -= 0.005 * onJaw * Math.exp(-(jaw * jaw) / 0.00012);
        shade -= 0.18 * onJaw * Math.exp(-(jaw * jaw) / 0.0001);

        // The mane: a raised band along the back of the neck, cut in strands.
        if (nearest >= maneFrom && nearest <= maneTo) {
            const reach = ramp(0.09, 0.035, d) * ramp(maneFrom, maneFrom + 6, nearest) * ramp(maneTo, maneTo - 4, nearest);
            const phase = along[nearest] * 21 + d * 9;
            const groove = Math.pow(0.5 + 0.5 * Math.cos(phase * Math.PI * 2), 3);
            z += reach * (0.013 - 0.011 * groove);
            shade -= reach * 0.45 * groove;
        }
        return { z: Math.max(z, 0.0015), shade: Math.max(0.35, shade) };
    }

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    ring.forEach(([x, y]) => {
        minX = Math.min(minX, x);
        maxX = Math.max(maxX, x);
        minY = Math.min(minY, y);
        maxY = Math.max(maxY, y);
    });
    const nx = Math.ceil((maxX - minX) / cell) + 2;
    const ny = Math.ceil((maxY - minY) / cell) + 2;
    const x0 = minX - cell;
    const y0 = minY - cell;

    const positions = [];
    const shades = [];
    const indices = [];
    const field = new Array((nx + 1) * (ny + 1));
    const front = new Int32Array((nx + 1) * (ny + 1)).fill(-1);
    const back = new Int32Array((nx + 1) * (ny + 1)).fill(-1);
    const rim = new Map();
    const at = (i, j) => j * (nx + 1) + i;

    for (let j = 0; j <= ny; j++) {
        for (let i = 0; i <= nx; i++) {
            const x = x0 + i * cell;
            const y = y0 + j * cell;
            const hit = probe(x, y);
            field[at(i, j)] = hit.d;
            if (hit.d > 0) {
                const { z, shade } = carve(x, y, hit.d, hit.nearest);
                front[at(i, j)] = positions.length / 3;
                positions.push(x, y, z);
                shades.push(shade);
                back[at(i, j)] = positions.length / 3;
                positions.push(x, y, -z);
                shades.push(shade);
            }
        }
    }
    // Where the outline crosses a grid edge both faces meet, at z = 0.
    function crossing(a, b, ai, aj, bi, bj) {
        const key = a < b ? `${a}:${b}` : `${b}:${a}`;
        if (rim.has(key)) return rim.get(key);
        const da = field[a];
        const db = field[b];
        const t = da / (da - db);
        const index = positions.length / 3;
        positions.push(x0 + (ai + (bi - ai) * t) * cell, y0 + (aj + (bj - aj) * t) * cell, 0);
        shades.push(1);
        rim.set(key, index);
        return index;
    }
    for (let j = 0; j < ny; j++) {
        for (let i = 0; i < nx; i++) {
            const corners = [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]];
            const ids = corners.map(([ci, cj]) => at(ci, cj));
            if (ids.every((id) => field[id] <= 0)) continue;
            const ringFront = [];
            const ringBack = [];
            for (let k = 0; k < 4; k++) {
                const a = ids[k];
                const b = ids[(k + 1) % 4];
                if (field[a] > 0) {
                    ringFront.push(front[a]);
                    ringBack.push(back[a]);
                }
                if ((field[a] > 0) !== (field[b] > 0)) {
                    const c = crossing(a, b, corners[k][0], corners[k][1], corners[(k + 1) % 4][0], corners[(k + 1) % 4][1]);
                    ringFront.push(c);
                    ringBack.push(c);
                }
            }
            for (let k = 1; k < ringFront.length - 1; k++) {
                indices.push(ringFront[0], ringFront[k], ringFront[k + 1]);
                indices.push(ringBack[0], ringBack[k + 1], ringBack[k]);
            }
        }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    const colour = new Float32Array(shades.length * 3);
    shades.forEach((s, i) => {
        colour[i * 3] = colour[i * 3 + 1] = colour[i * 3 + 2] = s;
    });
    geometry.setAttribute('color', new THREE.BufferAttribute(colour, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    return geometry;
}

function knightEar(side, segments) {
    const ear = lathe(outline([
        [0, 0],
        ['Q', 0.036, 0, 0.034, 0.036],
        ['Q', 0.03, 0.075, 0.006, 0.108],
        ['L', 0, 0.112],
    ], 6), Math.max(10, segments / 2));
    ear.scale(0.62, 1, 1);
    ear.rotateX(side * 0.16);
    ear.rotateZ(0.32);
    ear.translate(-0.012, 0.842, side * 0.044);
    return ear;
}

function buildKnight(segments, cell) {
    const base = knightFoot(Math.max(4, segments / 6));
    const footing = lathe(base, segments);
    return join([footing, knightHead(cell), knightEar(1, segments), knightEar(-1, segments)]);
}

// The rook's battlements: six merlons round the hollow top.
function buildRook(segments, detail) {
    const body = lathe(rookOutline(detail), segments);
    const parts = [body];
    const gap = 0.36;
    const span = (Math.PI * 2) / 6 - gap;
    for (let k = 0; k < 6; k++) {
        const shape = new THREE.Shape();
        shape.absarc(0, 0, 0.244, -span / 2, span / 2, false);
        shape.absarc(0, 0, 0.198, span / 2, -span / 2, true);
        shape.closePath();
        const merlon = new THREE.ExtrudeGeometry(shape, {
            depth: 0.07,
            bevelEnabled: true,
            bevelThickness: 0.008,
            bevelSize: 0.007,
            bevelSegments: 3,
            curveSegments: Math.max(4, segments / 8),
        });
        merlon.rotateX(-Math.PI / 2);
        // A merlon faces the front, and the cuts fall either side of it.
        merlon.rotateY(Math.PI / 2 + (k * Math.PI) / 3);
        merlon.translate(0, 0.692, 0);
        parts.push(merlon);
    }
    return join(parts);
}

// The bishop's mitre, with its slanting cut across the front.
function buildBishop(segments, detail) {
    const points = bishopOutline(detail);
    const geometry = lathe(points, segments);
    const position = geometry.attributes.position;
    // A V-shaped cut, sawn in from the front down to just past the middle.
    const tilt = (40 * Math.PI) / 180;
    const nx = Math.sin(tilt);
    const ny = Math.cos(tilt);
    const width = 0.017;
    const floor = -0.02;
    const depthAt = new Float32Array(position.count);
    for (let i = 0; i < position.count; i++) {
        const x = position.getX(i);
        const y = position.getY(i);
        const z = position.getZ(i);
        if (y < 0.67 || y > 0.93 || z <= floor) continue;
        const d = Math.abs(x * nx + (y - 0.81) * ny);
        // Dark a little past the lip too: the edge of a cut is in its shadow.
        depthAt[i] = 1 - ramp(width * 0.3, width * 1.3, d);
        if (d < width) position.setZ(i, z + (floor - z) * Math.pow(1 - d / width, 0.85));
    }
    geometry.computeVertexNormals();
    mendSeam(geometry, segments, points.length);
    // The cut is narrow and deep, so little light gets into it.
    let vertex = 0;
    return shaded(geometry, () => 1 - 0.9 * depthAt[vertex++]);
}

// The queen's coronet: the rim rises in eight points, each with a pearl.
function buildQueen(segments, detail) {
    const points = queenOutline(detail);
    const geometry = lathe(points, segments);
    const position = geometry.attributes.position;
    for (let i = 0; i < position.count; i++) {
        const x = position.getX(i);
        const y = position.getY(i);
        const z = position.getZ(i);
        const r = Math.hypot(x, z);
        if (y < 0.9 || r < 0.1) continue;
        const angle = Math.atan2(x, z);
        const peak = Math.pow(0.5 + 0.5 * Math.cos(angle * 8), 2.2);
        const reach = ramp(0.9, 0.985, y) * ramp(0.1, 0.17, r);
        position.setY(i, y + reach * (0.05 * peak - 0.018));
    }
    geometry.computeVertexNormals();
    mendSeam(geometry, segments, points.length);
    const parts = [geometry];
    for (let k = 0; k < 8; k++) {
        const angle = (k * Math.PI) / 4;
        const pearl = new THREE.SphereGeometry(0.024, Math.max(8, segments / 3), Math.max(6, segments / 5));
        pearl.translate(Math.sin(angle) * 0.2, 1.03, Math.cos(angle) * 0.2);
        parts.push(pearl);
    }
    return join(parts);
}

// The king's crown and its cross pattée, which faces the front.
function buildKing(segments, detail) {
    const body = lathe(kingOutline(detail), segments);
    const shape = new THREE.Shape();
    const cross = [
        [-0.022, 0], [0.022, 0], [0.017, 0.082], [0.07, 0.074], [0.076, 0.132], [0.017, 0.124],
        [0.024, 0.2], [-0.024, 0.2], [-0.017, 0.124], [-0.076, 0.132], [-0.07, 0.074], [-0.017, 0.082],
    ];
    shape.moveTo(...cross[0]);
    cross.slice(1).forEach((point) => shape.lineTo(...point));
    shape.closePath();
    const top = new THREE.ExtrudeGeometry(shape, {
        depth: 0.03,
        bevelEnabled: true,
        bevelThickness: 0.011,
        bevelSize: 0.008,
        bevelSegments: 4,
    });
    top.translate(0, 1.108, -0.015);
    const knob = new THREE.SphereGeometry(0.036, Math.max(10, segments / 2), 8);
    knob.scale(1, 0.7, 1);
    knob.translate(0, 1.118, 0);
    return join([body, knob, top]);
}

/**
 * The six pieces as geometries. segments is the number of faces round a
 * turned piece; cell is the size of the grid the knight's head is carved on
 * (smaller is finer and slower to build).
 */
export function buildGeometry(segments = 40, cell = 0.011) {
    const detail = Math.max(4, Math.round(segments / 5));
    return {
        p: join([lathe(pawnOutline(detail), segments)]),
        r: buildRook(segments, detail),
        b: buildBishop(segments, detail),
        q: buildQueen(segments, detail),
        k: buildKing(segments, detail),
        n: buildKnight(segments, cell),
    };
}

// Turned boxwood and ebony. A little noise along the growth rings of the
// wood darkens the colour here and there, so the pieces look turned from a
// log and not cast; it is too faint to notice from across the board.
const GRAIN = `
varying vec3 vGrainAt;
uniform float grainDepth;
float grainHash(vec3 p) {
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float grainNoise(vec3 x) {
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(mix(grainHash(i), grainHash(i + vec3(1, 0, 0)), f.x), mix(grainHash(i + vec3(0, 1, 0)), grainHash(i + vec3(1, 1, 0)), f.x), f.y),
        mix(mix(grainHash(i + vec3(0, 0, 1)), grainHash(i + vec3(1, 0, 1)), f.x), mix(grainHash(i + vec3(0, 1, 1)), grainHash(i + vec3(1, 1, 1)), f.x), f.y),
        f.z);
}
float woodGrain(vec3 p) {
    vec2 c = p.xz - vec2(0.85, 0.4);
    float r = length(c) + 0.04 * grainNoise(p * vec3(4.0, 1.0, 4.0)) + 0.01 * grainNoise(p * 26.0);
    float ring = fract(r * 30.0);
    float late = smoothstep(0.62, 0.9, ring) * (1.0 - smoothstep(0.9, 1.0, ring));
    float fleck = grainNoise(p * vec3(120.0, 9.0, 120.0));
    return 1.0 - grainDepth * (0.75 * late + 0.25 * fleck);
}
`;
function withGrain(material, depth) {
    material.onBeforeCompile = (shader) => {
        shader.uniforms.grainDepth = { value: depth };
        shader.vertexShader = `varying vec3 vGrainAt;\n${shader.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n    vGrainAt = position;')}`;
        // The vertex shade darkens the colour (three.js does that) and here
        // also dulls the gloss, so a hollow does not catch the light.
        shader.fragmentShader = GRAIN + shader.fragmentShader
            .replace('#include <color_fragment>', '#include <color_fragment>\n    diffuseColor.rgb *= woodGrain(vGrainAt);')
            .replace('#include <lights_physical_fragment>', '#include <lights_physical_fragment>\n    material.specularColor *= vColor.r * vColor.r;\n    material.specularF90 *= vColor.r;\n    #ifdef USE_CLEARCOAT\n    material.clearcoat *= vColor.r * vColor.r;\n    #endif');
    };
    material.customProgramCacheKey = () => `grain-${depth}`;
    return material;
}

export function buildMaterials() {
    return {
        w: withGrain(new THREE.MeshPhysicalMaterial({
            color: 0xf0e2c4, vertexColors: true, metalness: 0, roughness: 0.42,
            clearcoat: 0.55, clearcoatRoughness: 0.3, sheen: 0.25, sheenRoughness: 0.6, sheenColor: 0xfff4dc,
        }), 0.09),
        b: withGrain(new THREE.MeshPhysicalMaterial({
            color: 0x1c1512, vertexColors: true, metalness: 0, roughness: 0.34,
            clearcoat: 1, clearcoatRoughness: 0.12,
        }), 0.22),
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
