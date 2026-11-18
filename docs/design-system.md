# Design system

Every page in Checkora is built from one base template and one stylesheet. This page says how to use them, so a new page looks like the rest without anyone copying a navbar again.

## The base template

A page extends `game/base.html` and fills its blocks:

```django
{% extends 'game/base.html' %}
{% load static %}

{% block title %}Puzzles · Checkora{% endblock %}
{% block styles %}<link rel="stylesheet" href="{% static 'game/css/learn.css' %}">{% endblock %}

{% block content %}
<div class="wrap page">
    <header class="page-head">
        <a class="back-link" href="{% url 'landing' %}">Home</a>
        <h1>Puzzles</h1>
        <p>One line that says what the page is for.</p>
    </header>
    ...
</div>
{% endblock %}

{% block scripts %}<script src="{% static 'game/js/puzzles.js' %}"></script>{% endblock %}
```

The base template brings the fonts, the theme script (in `<head>`, so there is no flash of the wrong theme), the navbar, Django messages, the footer, toasts and the shared behaviour in `app.js`. A page never writes its own `<html>`, navbar, footer, font links or theme toggle. The one exception is `game/templates/500.html`, which stands alone so that it still renders when the session or the database is what failed.

Blocks: `title`, `description`, `head` (extra meta tags), `styles`, `body_class`, `main_class`, `messages`, `content`, `footer`, `scripts`. Override `nav` or `footer` with an empty block only for a page that truly has no chrome.

## Tokens

Colours, type and spacing are CSS variables in `game/static/game/css/app.css`. Use them and nothing else: no hex colours in page stylesheets, no inline `style` colours, no extra font families.

| Token | Use |
| --- | --- |
| `--ink-0` to `--ink-3` | Page background, surface, raised surface, hover |
| `--line`, `--line-strong` | Hairlines and stronger borders |
| `--title`, `--text`, `--muted` | Headings, body text, secondary text |
| `--gold`, `--gold-bright`, `--gold-deep`, `--on-gold`, `--gold-wash` | The accent, its gradient ends, text on it, and a tint of it |
| `--check`, `--good`, `--info` (and `--check-wash`, `--good-wash`) | Errors and check, success, information |
| `--font-sans`, `--font-serif`, `--font-mono` | Outfit for text, Instrument Serif for the italic accent in headings, JetBrains Mono for notation, clocks and labels |
| `--radius-sm`, `--radius`, `--radius-lg`, `--pad` | Corners and the page gutter |
| `--ease-out`, `--ease-spring` | Easing for transitions |

Both themes are defined there. A page that uses only tokens works in light and dark without any rule of its own.

## Components

| Class | What it is |
| --- | --- |
| `.wrap`, `.wrap--narrow`, `.wrap--wide` | Centred page width |
| `.page`, `.section` | Vertical padding for an app page, and for a landing section |
| `.page-head`, `.back-link` | Page title block and the link back |
| `.stack`, `.cluster`, `.grid`, `.spread` | Layout helpers; set `--gap`, and `--min` for the grid's column width |
| `.eyebrow`, `.display`, `.lede`, `.serif`, `.mono`, `.muted`, `.gold`, `.text-link` | Type |
| `.button` with `--primary`, `--ghost`, `--danger`, `--sm`, `--lg`, `--block` | Buttons and button-styled links |
| `.icon-button` | Round icon button; give it an `aria-label` |
| `.panel`, `.panel--raised`, `.panel--link` | Cards |
| `.stat` with `.stat__value` and `.stat__label` | A number with its label |
| `.chip` with `--gold`, `--good`, `--check` | Small labels and tags |
| `.field`, `.input`, `.field__hint`, `.field__error`, `.check` | Forms. A `.field` wraps a `<label>` and its control |
| `.notice` with `--error`, `--success`, `--warning` | Inline messages |
| `.table-wrap` and `.data-table` | Tables |
| `.tabs` | Tab or filter switch; mark the current one with `.is-active`, `aria-selected` or `aria-current` |
| `dialog.modal` with `.modal__head` and `.modal__body` | Dialogs. Open with `data-open-dialog="id"`, close with `data-close-dialog` |
| `.menu` with `data-menu` and `data-menu-button` | Dropdown menus |
| `.empty` | Empty state |
| `.progress` | Progress bar; set the inner `<span>` width |
| `.avatar`, `.avatar--lg`, `.avatar--xl` | User picture or initial. Draw it with the `{% avatar %}` tag below, not by hand |
| `.rank-badge` | A player's rank with its piece; drawn by `{% rank_badge %}` |

## Players

`game/templatetags/players.py` has two tags for showing a player. Load them with `{% load players %}`.

- `{% avatar user "avatar--lg" %}` draws the player's picture: a preset piece, an upload served from `/u/<id>/avatar/`, or the first letter of the name. The second argument adds classes to the `.avatar` element. The picture is hidden from screen readers, because the name is always written next to it.
- `{% rank_badge rating games_played %}` draws the rank for a rating, from Pawn to King, with a `?` while the rating is still provisional.

A page that lists many players should load them with `select_related('profile')` and `.defer('profile__avatar')`. Otherwise `{% avatar %}` fetches each profile on its own, without the picture data.

## Motion

- `data-reveal` on an element makes it rise in when it scrolls into view. `style="--i: 2"` delays it, for a staggered group. Variants: `data-reveal="left"` and `data-reveal="scale"`.
- `data-tilt` on a `.panel` makes it lean toward the pointer. The value is the largest angle in degrees.
- Page-to-page navigation cross-fades through the View Transitions API where the browser has it.
- Everything above switches itself off under `prefers-reduced-motion`.

## Performance tiers

`game/static/game/js/perf.js` runs in the `<head>` of every page and sets `data-perf="high"` or `data-perf="low"` on `<html>` before the first paint. High is the full site. Low keeps every piece of content and every layout, and drops the expensive effects: blur, large glows, tilt, long or looping animations, the 3D pieces (the flat SVG piece shows instead), and on the landing board the shadows, antialiasing and pointer light.

How the tier is chosen:

- `?perf=low` or `?perf=high` in the URL forces a tier for the rest of the browser session; `?perf=auto` goes back to detection.
- Otherwise the first guess comes from what the browser reports: a software renderer or an old integrated GPU, few CPU cores together with little memory, or the data saver setting mean low. Apple GPUs and anything recent start as high.
- While the page is moving, frames are counted in one-second windows. Three slow windows (under 40 frames a second) move the page to low for the rest of the session. It never moves back up by itself. A steady cadence near 30 frames a second is not counted, because that is a battery-saving cap and not lag.

Effects that are expensive go under `[data-perf='low']` in the page's stylesheet, at the end of the file. Scripts read the tier from `window.checkoraPerf` (`tier`, `low`, `wants3D(kind)`, `onDemote(listener)`); a running animation should stop when `onDemote` fires. `prefers-reduced-motion` is separate and still applies on both tiers.

## 3D

`game/static/game/js/scene3d.js` holds the three.js scenes. It needs an import map for `three` in the page's `head` block and a module script:

```django
{% block head %}
<script type="importmap">{ "imports": { "three": "{% static 'game/vendor/three/three.module.min.js' %}" } }</script>
{% endblock %}
```

```js
import { shouldMount3D, mountPiece } from './scene3d.js';
if (shouldMount3D('piece')) mountPiece(canvas, { type: 'k', color: 'w' });
else showFlatPiece();
```

`shouldMount3D(kind)` is the one place that decides whether a scene is mounted: it asks the performance tier and checks for WebGL. A page that imports `scene3d.js` lazily can ask `window.checkoraPerf.wants3D(kind)` first and skip downloading three.js on the low tier.

`mountHero(canvas)` is the landing page board; its floor and fog follow the light and dark theme. `mountPiece(canvas, { type, color, fallen })` is one piece turning on a plinth, for the smaller pages. Both pause when they are off screen, and both need a flat fallback for the low tier and for browsers without WebGL.

## Piece images

The pieces you see on the flat boards are photographs of the 3D set in `scene3d.js`: ivory and ebony Staunton pieces, rendered in Chrome and saved as WebP with transparency. There are two sets of the same twelve pieces:

- `game/static/game/pieces/staunton/<colour><type>.webp` (256 px) is for boards. Every piece is framed the same, so a king stands taller than a pawn, and each picture carries the soft shadow the piece throws. The picture is framed for the king, so on a board it is drawn a little larger than its square and set high; see `.square > .piece` in `play.css` and the boards in `learn.css`.
- `game/static/game/pieces/staunton-single/<colour><type>.webp` (192 px) is for a piece on its own: icons, the pieces taken in a game, the promotion choice, the rank badges, the profile pictures a player can pick, and the flat stand-in shown where a turning 3D piece is not drawn. Each piece fills its picture.

In a template use `{% static 'game/pieces/staunton-single/wn.webp' %}`; in JavaScript read the prefix from `document.documentElement.dataset.static`. Knights face left in both colours.

The play page still offers the older flat SVG sets as choices in its settings, in `game/static/game/pieces/<style>/<colour><type>.svg` with styles `classic`, `wood` and `outline`. board.js picks the extension per style.

To change a piece, change its model in `scene3d.js` and render the sets again (Playwright and Google Chrome are needed; Playwright is not a project dependency, so point `PLAYWRIGHT` at a copy of it):

```sh
PLAYWRIGHT=/path/to/node_modules/playwright node scripts/render_pieces.mjs
PLAYWRIGHT=/path/to/node_modules/playwright node scripts/render_pieces.mjs --single
```

## The wooden board

The default board ("gilded") and every board outside the play page are maple and walnut in a walnut frame. The wood is drawn from seeded noise by `scripts/render_wood.mjs` into `game/static/game/board/` (`maple.webp`, `walnut.webp`, `frame.webp`). Each square shows its own part of the plank, so the board does not look tiled; a square's state (last move, selection, a hint) is a tint laid over the wood, not a new colour. The square textures hold the plank twice, the second copy turned half round, which is what a flipped board shows.

## Rules of thumb

- Page-specific CSS goes in a page stylesheet loaded through the `styles` block, and only describes that page's layout.
- No `<style>` blocks and no `style` attributes for colour, font or spacing that a class already covers.
- Interactive things are `<a>` or `<button>`, never a `div` with `onclick`.
- Every form field has a label, every image has `alt`, and focus stays visible.
- Check a new page at 375px and 1440px, in both themes.
