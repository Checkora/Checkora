---
title: Add About page and anchor to navbar
labels: enhancement, good first issue, GSSOC'26
assignee: "<GITHUB_USERNAME>"
---

## Summary

Create a responsive About page for Checkora that matches the existing dark theme and golden accent styling, and anchor it from the navbar and footer.

## Current State

- The navbar contains an "About" link that previously pointed to `#hero` on the landing page.
- A new route and template were added locally on branch `feature/about-page`:
  - `game/templates/game/about.html`
  - `game/static/game/css/landing.css` (added about styles)
  - `game/views.py` (new `about` view)
  - `game/urls.py` (new `about/` route)
  - `game/templates/game/landing.html` (nav/footer link updated)

## Proposed Work

1. Keep the current dark/gold theme and reuse `landing.css` for global styles.
2. Add semantic HTML sections: Introduction, Features, AI Engine, Tech Stack, Contribution.
3. Make the page fully responsive (grid + media queries) and lightweight (no new dependencies).
4. Anchor the navbar and footer links to `/about/`.

## How to test locally

1. Checkout the branch: `git checkout feature/about-page` (branch already created in the workspace).
2. Ensure dependencies are installed: `pip install -r requirements.txt`.
3. Run migrations: `python manage.py migrate`.
4. Start the dev server: `python manage.py runserver` and open `http://localhost:8000/about/`.

## Files changed (local)

- `game/templates/game/about.html` (new)
- `game/static/game/css/landing.css` (appended about styles)
- `game/templates/game/landing.html` (nav/footer link to about)
- `game/views.py` (added `about` view)
- `game/urls.py` (added `about/` route)

## Notes for maintainers

- The about page reuses the landing stylesheet to avoid duplication and maintain visual consistency.
- If you'd like the page to be added to other places (board header, footer variants), I can prepare a small PR to propagate the link.

## Assignment

Please replace `<GITHUB_USERNAME>` above with your GitHub username to claim this issue, or tell me your username and I'll open and assign the issue on the remote repository for you.

---
Created by automation to capture local changes and enable claiming under GSSOC'26.
