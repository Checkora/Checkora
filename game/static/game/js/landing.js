// The landing page: starts the 3D board in the hero, prints the moves as
// they are played, and runs the alpha-beta demonstration.
import { mountHero, shouldMount3D } from './scene3d.js';

const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function startHero() {
    const hero = document.querySelector('.hero');
    const canvas = document.getElementById('heroCanvas');
    const ticker = document.getElementById('heroTicker');
    const list = document.getElementById('heroMoves');
    if (!hero || !canvas) return;

    // The flat board stands in where there is no WebGL, on the low
    // performance tier when the GPU is a software renderer, and when the 3D
    // board finds it cannot keep up even on its low settings.
    const flat = () => {
        hero.classList.add('is-flat');
        if (ticker) ticker.hidden = true;
    };
    if (!shouldMount3D('hero')) {
        flat();
        return;
    }

    try {
        mountHero(canvas, {
            onFail: flat,
            onPly({ ply, san }) {
                if (!list) return;
                if (ply === 0) {
                    list.replaceChildren();
                    return;
                }
                const item = document.createElement('li');
                const number = Math.ceil(ply / 2);
                item.textContent = ply % 2 ? `${number}. ${san}` : `${number}… ${san}`;
                list.append(item);
                while (list.children.length > 6) list.firstElementChild.remove();
            },
        });
        if (ticker) ticker.hidden = false;
    } catch (error) {
        flat();
    }
}

// A three-level game tree searched with alpha-beta. The leaf values are
// drawn at random each round, so the pruning shown is whatever the
// algorithm really does with them.
function startTree() {
    const svg = document.getElementById('searchTree');
    if (!svg) return;
    const NS = 'http://www.w3.org/2000/svg';
    const out = {
        seen: document.getElementById('treeSeen'),
        pruned: document.getElementById('treePruned'),
        best: document.getElementById('treeBest'),
    };
    const make = (name, attrs, parent = svg) => {
        const element = document.createElementNS(NS, name);
        Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
        parent.append(element);
        return element;
    };

    const rootAt = { x: 260, y: 44 };
    const midAt = [0, 1, 2].map((i) => ({ x: 92 + i * 168, y: 150 }));
    const leafAt = Array.from({ length: 9 }, (_, i) => ({ x: 44 + i * 54, y: 270 }));

    [['MAX · White to move', 44], ['MIN · Black replies', 150], ['Evaluation', 270]].forEach(([text, y]) => {
        make('text', { class: 'label', x: -150, y: y + 4 }).textContent = text;
    });

    const edges = { mid: [], leaf: [] };
    midAt.forEach((mid, i) => {
        edges.mid.push(make('line', { class: 'edge', x1: rootAt.x, y1: rootAt.y, x2: mid.x, y2: mid.y }));
        [0, 1, 2].forEach((j) => {
            const leaf = leafAt[i * 3 + j];
            edges.leaf.push(make('line', { class: 'edge', x1: mid.x, y1: mid.y, x2: leaf.x, y2: leaf.y }));
        });
    });

    const node = (at, shape) => {
        const group = make('g', { class: 'node' });
        if (shape === 'leaf') make('rect', { x: at.x - 19, y: at.y - 16, width: 38, height: 32, rx: 8 }, group);
        else make('circle', { cx: at.x, cy: at.y, r: 21 }, group);
        const text = make('text', { x: at.x, y: at.y }, group);
        return { group, text };
    };
    const rootNode = node(rootAt, 'root');
    const midNodes = midAt.map((at) => node(at, 'mid'));
    const leafNodes = leafAt.map((at) => node(at, 'leaf'));

    const everything = () => [rootNode.group, ...midNodes.map((n) => n.group), ...leafNodes.map((n) => n.group), ...edges.mid, ...edges.leaf];
    const signed = (value) => (value > 0 ? `+${value}` : String(value));

    function round() {
        const values = Array.from({ length: 9 }, () => Math.round(Math.random() * 18 - 9));
        everything().forEach((element) => element.classList.remove('is-seen', 'is-best', 'is-pruned'));
        rootNode.text.textContent = '?';
        midNodes.forEach((n) => (n.text.textContent = '?'));
        leafNodes.forEach((n, i) => (n.text.textContent = signed(values[i])));

        // Work the search out first, as a list of steps to show.
        const steps = [];
        let alpha = -Infinity;
        let bestMid = -1;
        let seen = 0;
        let pruned = 0;
        for (let i = 0; i < 3; i++) {
            let beta = Infinity;
            steps.push(() => {
                edges.mid[i].classList.add('is-seen');
                midNodes[i].group.classList.add('is-seen');
            });
            for (let j = 0; j < 3; j++) {
                const k = i * 3 + j;
                if (beta <= alpha) {
                    pruned += 1;
                    const count = pruned;
                    steps.push(() => {
                        edges.leaf[k].classList.add('is-pruned');
                        leafNodes[k].group.classList.add('is-pruned');
                        out.pruned.textContent = count;
                    });
                    continue;
                }
                seen += 1;
                beta = Math.min(beta, values[k]);
                const count = seen;
                const shown = beta;
                steps.push(() => {
                    edges.leaf[k].classList.add('is-seen');
                    leafNodes[k].group.classList.add('is-seen');
                    midNodes[i].text.textContent = signed(shown);
                    out.seen.textContent = count;
                });
            }
            if (beta > alpha) {
                alpha = beta;
                bestMid = i;
            }
            const best = alpha;
            steps.push(() => {
                rootNode.group.classList.add('is-seen');
                rootNode.text.textContent = signed(best);
            });
        }
        const answer = alpha;
        steps.push(() => {
            rootNode.group.classList.add('is-best');
            midNodes[bestMid].group.classList.add('is-best');
            edges.mid[bestMid].classList.add('is-best');
            out.best.textContent = signed(answer);
        });

        out.seen.textContent = '0';
        out.pruned.textContent = '0';
        out.best.textContent = '–';
        if (calm) {
            steps.forEach((step) => step());
            return;
        }
        steps.forEach((step, index) => window.setTimeout(step, 500 + index * 420));
        window.setTimeout(round, 500 + steps.length * 420 + 3200);
    }

    // Start when the tree scrolls into view, not before.
    const observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
            observer.disconnect();
            round();
        }
    }, { threshold: 0.3 });
    observer.observe(svg);
}

// Meet the pieces: one piece in the middle of a small board, the squares it
// can reach marked one after another. The board turns to the next piece by
// itself until someone picks one.
const PIECES = {
    k: { name: 'King', rule: 'One square in any direction, never onto a square that is attacked. Once a game it can castle with a rook.', meta: 'Worth the game' },
    q: { name: 'Queen', rule: 'Any number of squares in a straight line or along a diagonal, as long as nothing stands in the way.', meta: 'Worth 9 pawns' },
    r: { name: 'Rook', rule: 'Any number of squares along its rank or its file. It also moves when the king castles.', meta: 'Worth 5 pawns' },
    b: { name: 'Bishop', rule: 'Any number of squares along a diagonal, so it stays on the colour it started on.', meta: 'Worth 3 pawns' },
    n: { name: 'Knight', rule: 'Two squares one way and one to the side, an L. It is the only piece that jumps over others.', meta: 'Worth 3 pawns' },
    p: { name: 'Pawn', rule: 'Forward one square, or two from its first square, and captures one square diagonally forward. On the last rank it promotes.', meta: 'Worth 1 pawn' },
};

function reach(type, row, col) {
    const inside = (r, c) => r >= 0 && r < 8 && c >= 0 && c < 8;
    const slide = (directions) => directions.flatMap(([dr, dc]) => {
        const squares = [];
        for (let r = row + dr, c = col + dc; inside(r, c); r += dr, c += dc) squares.push([r, c]);
        return squares;
    });
    const step = (offsets) => offsets.map(([dr, dc]) => [row + dr, col + dc]).filter(([r, c]) => inside(r, c));
    const straight = [[1, 0], [-1, 0], [0, 1], [0, -1]];
    const diagonal = [[1, 1], [1, -1], [-1, 1], [-1, -1]];
    switch (type) {
        case 'k': return step([...straight, ...diagonal]);
        case 'q': return slide([...straight, ...diagonal]);
        case 'r': return slide(straight);
        case 'b': return slide(diagonal);
        case 'n': return step([[2, 1], [2, -1], [-2, 1], [-2, -1], [1, 2], [1, -2], [-1, 2], [-1, -2]]);
        default: return step([[-1, 0], [-2, 0]]);
    }
}

function startPieces() {
    const board = document.getElementById('miniBoard');
    const picks = Array.from(document.querySelectorAll('.piece-pick'));
    if (!board || !picks.length) return;
    const base = `${document.documentElement.dataset.static || '/static/game/'}pieces/staunton/`;
    const name = document.getElementById('pieceName');
    const rule = document.getElementById('pieceRule');
    const meta = document.getElementById('pieceMeta');

    const squares = Array.from({ length: 64 }, (_, i) => {
        const square = document.createElement('span');
        if ((Math.floor(i / 8) + (i % 8)) % 2) square.classList.add('is-dark');
        board.append(square);
        return square;
    });
    const at = (r, c) => squares[r * 8 + c];

    function show(type) {
        squares.forEach((square) => {
            square.replaceChildren();
            square.classList.remove('is-target', 'is-capture');
            square.style.removeProperty('--d');
        });
        // The pawn starts on its own square so its double step shows; the
        // others stand in the middle of the board.
        const [row, col] = type === 'p' ? [6, 3] : [4, 3];
        const piece = new Image();
        piece.src = `${base}w${type}.webp`;
        piece.alt = '';
        at(row, col).append(piece);
        reach(type, row, col).forEach(([r, c]) => {
            const square = at(r, c);
            square.classList.add('is-target');
            square.style.setProperty('--d', Math.max(Math.abs(r - row), Math.abs(c - col)));
        });
        if (type === 'p') {
            // Two black pawns to take, one square diagonally forward.
            [[5, 2], [5, 4]].forEach(([r, c], i) => {
                const target = new Image();
                target.src = `${base}bp.webp`;
                target.alt = '';
                at(r, c).append(target);
                at(r, c).classList.add('is-capture');
                at(r, c).style.setProperty('--d', i + 2);
            });
        }
        const text = PIECES[type];
        name.textContent = text.name;
        rule.textContent = text.rule;
        meta.textContent = text.meta;
        picks.forEach((pick) => pick.setAttribute('aria-pressed', pick.dataset.piece === type ? 'true' : 'false'));
    }

    const order = picks.map((pick) => pick.dataset.piece);
    let current = 0;
    let timer = 0;
    const lowTier = () => document.documentElement.dataset.perf === 'low';
    function cycle() {
        window.clearTimeout(timer);
        if (calm || lowTier()) return;
        timer = window.setTimeout(() => {
            current = (current + 1) % order.length;
            show(order[current]);
            cycle();
        }, 4200);
    }
    picks.forEach((pick, index) => {
        pick.addEventListener('click', () => {
            window.clearTimeout(timer);
            current = index;
            show(pick.dataset.piece);
            // A choice stops the tour for a while, then it carries on.
            timer = window.setTimeout(cycle, 9000);
        });
    });

    show(order[0]);
    const observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) cycle();
        else window.clearTimeout(timer);
    }, { threshold: 0.25 });
    observer.observe(board);
}

// Specks of gold that drift up through the hero and catch the light.
function startDust() {
    const canvas = document.getElementById('heroDust');
    const perf = window.checkoraPerf;
    if (!canvas || calm || (perf && perf.low)) {
        canvas?.remove();
        return;
    }
    const context = canvas.getContext('2d');
    const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
    let width = 0;
    let height = 0;
    let colour = '#f2b93b';
    const motes = [];

    function size() {
        width = canvas.clientWidth;
        height = canvas.clientHeight;
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        colour = getComputedStyle(document.documentElement).getPropertyValue('--gold').trim() || colour;
        const wanted = Math.round(Math.min(90, (width * height) / 16000));
        while (motes.length < wanted) motes.push(spawn(true));
        motes.length = wanted;
    }
    function spawn(anywhere) {
        return {
            x: Math.random() * width,
            y: anywhere ? Math.random() * height : height + 10,
            r: 0.6 + Math.random() * 1.8,
            rise: 0.12 + Math.random() * 0.38,
            sway: Math.random() * Math.PI * 2,
            glow: Math.random() * Math.PI * 2,
        };
    }

    let running = false;
    let frame = 0;
    let release = null;
    function draw(now) {
        if (!running) return;
        context.clearRect(0, 0, width, height);
        context.fillStyle = colour;
        for (const mote of motes) {
            mote.y -= mote.rise;
            mote.x += Math.sin(now / 1800 + mote.sway) * 0.15;
            if (mote.y < -10) Object.assign(mote, spawn(false));
            context.globalAlpha = 0.25 + 0.55 * (0.5 + 0.5 * Math.sin(now / 700 + mote.glow));
            context.beginPath();
            context.arc(mote.x, mote.y, mote.r, 0, Math.PI * 2);
            context.fill();
        }
        context.globalAlpha = 1;
        frame = requestAnimationFrame(draw);
    }
    function run(on) {
        if (on === running) return;
        running = on;
        if (on) {
            release = perf?.hold?.() || null;
            frame = requestAnimationFrame(draw);
        } else {
            cancelAnimationFrame(frame);
            release?.();
            release = null;
        }
    }

    size();
    new ResizeObserver(size).observe(canvas);
    document.addEventListener('checkora:theme', size);
    const observer = new IntersectionObserver((entries) => run(entries.some((entry) => entry.isIntersecting)));
    observer.observe(canvas);
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            run(false);
            return;
        }
        const box = canvas.getBoundingClientRect();
        run(box.bottom > 0 && box.top < window.innerHeight);
    });
    perf?.onDemote?.(() => {
        run(false);
        observer.disconnect();
        canvas.remove();
    });
}

startHero();
startTree();
startPieces();
startDust();
