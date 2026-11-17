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

startHero();
startTree();
