# Checkora Accessibility and ARIA Design Patterns

This document defines the accessibility standards, keyboard navigation controls, and ARIA (Accessible Rich Internet Applications) specifications designed into the Checkora web game. 

Checkora prioritizes digital inclusion, aligning its interactive boards and control overlays with Web Content Accessibility Guidelines (WCAG) 2.1 AA requirements.

---

## 1. Keyboard Navigation Design

A robust keyboard navigation paradigm ensures that players who rely on screen readers or have motor impairments can play checkers and chess games seamlessly.

### Navigation Hierarchy & Tab Order

Tab order flows sequentially from top-to-bottom and left-to-right through the main sections of the user interface:

1.  **Header Navigation**: Skip-to-content link, logo, home link, match settings.
2.  **Game Control Panel**: Turn indicator, undo button, draw/resign buttons, timer.
3.  **Active Board Workspace**: Interactive game square elements.
4.  **Move History Logs**: Collapsible sidebar listing algebraic game notations.

---

### Board Interaction Matrix

Interactive board grids are configured as accessible tab matrices.

| Input Key | Action Taken | Focus Destination / Event |
| :--- | :--- | :--- |
| **Tab** | Move to next interface element | Cycle between settings panel, active board grid, and history log. |
| **Shift + Tab** | Move to previous interface element | Traverse backward in focus chain. |
| **Arrow Keys (`←`, `↑`, `→`, `↓`)** | Grid traversal | Focus adjacent square in specified direction on the 2D chess board. |
| **Space** / **Enter** | Square Selection | Select currently focused piece, or confirm target drop-off cell. |
| **Escape** | Cancel Selection | Deselect active board square, cancelling current drag-and-drop. |

---

## 2. ARIA Roles & State Mapping

Custom HTML components use explicit ARIA attributes to map real-time board states to screen readers and assistive devices.

### Board and Grid Layouts
Interactive boards use a combination of `grid`, `row`, and `gridcell` roles to represent their structured 2D tabular formats.

```html
<!-- Main 8x8 Board Element -->
<div 
  class="board" 
  role="grid" 
  aria-label="Checkers Game Board" 
  aria-readonly="true" 
  aria-colcount="8" 
  aria-rowcount="8"
>
  <!-- Board Row -->
  <div class="row" role="row" aria-rowindex="1">
    <!-- Grid Square (Cell) -->
    <div 
      class="square dark" 
      role="gridcell" 
      id="square-a1"
      aria-colindex="1"
      aria-label="a1 square: empty"
      tabindex="0"
    ></div>
  </div>
</div>
```

---

### Pieces and Dynamic Selection States

Game pieces utilize interactive ARIA attributes to convey whether they represent white or black teams, active states, and selection availability:

| ARIA Attribute | Target Element | Dynamic State |
| :--- | :--- | :--- |
| `role="button"` | Piece wrapper | Designates that the piece is a clickable/interactive element. |
| `aria-grabbed` / `aria-selected` | Selection wrapper | Switches to `true` when a piece is clicked/focused to initiate a move. |
| `aria-live="polite"` | Dynamic message container | Read aloud by screen readers when game statuses, checks, or turns update. |
| `aria-describedby` | Piece wrapper | Points to contextual rules (e.g., "White King Piece"). |

```html
<!-- Example of a Focused White Piece on A1 Square -->
<div 
  class="piece white-king" 
  role="button" 
  aria-label="White King on A1"
  aria-selected="true" 
  tabindex="0"
>
  👑
</div>
```

---

## 3. Screen Reader Turn Logs

Real-time moves and events are reported to assistive interfaces via ARIA live containers:

```html
<div 
  id="game-announcements" 
  class="sr-only" 
  role="status" 
  aria-live="assertive" 
  aria-atomic="true"
>
  <!-- Dynamically injected: "White moves pawn to e4. Black turn." -->
</div>
```

---

## 4. Accessibility Testing Checklists

*   **Keyboard Accessibility**: Verify that a player can start a game, select and move a piece, check/verify opponent moves, and resign/draw purely using a keyboard.
*   **Contrast Standards**: Confirm all text and game-piece elements against background colors achieve a minimum contrast ratio of 4.5:1.
*   **Focus Ring Indicator**: Verify that a bright, high-visibility focus ring outline is always visible when elements are targeted via keyboard navigation.
