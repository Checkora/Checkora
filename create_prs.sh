#!/bin/bash
set -e
cd /c/Users/Abhinav/Checkora

echo "=== Creating PR branches ==="

create_pr() {
    local branch="$1"
    local title="$2"
    local files="$3"
    echo ""
    echo "--- $branch ---"
    git checkout -b "$branch" main 2>/dev/null
    for f in $files; do
        git checkout "stash@{0}" -- "$f" 2>/dev/null
    done
    git add -A
    git commit -m "$title" 2>/dev/null
    git push fork "$branch" 2>/dev/null
    gh pr create --repo Checkora/Checkora \
        --head "Youngmaster0304:$branch" \
        --title "$title" \
        --body "Automated PR for Checkora contribution." 2>/dev/null
    echo "  -> Done"
    git checkout main 2>/dev/null
}

# PR1: C++ engine board validation
create_pr "fix/cpp-engine-board-validation" \
    "fix(engine): add board string input validation in loadBoard" \
    "game/engine/main.cpp"

# PR 2: Engine binary path caching (only the caching part of engine.py)
# This needs manual editing, skip for now - will handle separately

# PR 3: Open Graph tags for board page
create_pr "feat/og-tags-board-page" \
    "feat: add Open Graph and Twitter Card meta tags to board page" \
    "game/templates/game/board.html"

# PR 4: prefers-reduced-motion for board
create_pr "feat/reduced-motion-board" \
    "feat(css): add prefers-reduced-motion support for board animations" \
    "game/static/game/css/board.css"

# PR 5: Toast stacking + ARIA
create_pr "fix/toast-stacking-aria" \
    "fix(toast): add stacking max-height, ARIA live region, and reduced-motion fallback" \
    "game/static/game/css/toast.css game/static/game/js/toast.js"

# PR 7: db_index on played_at
create_pr "perf/db-index-played-at" \
    "perf(models): add db_index on GameResult.played_at for query performance" \
    "game/models.py"

# PR 8: Atomic F() expressions for XP
create_pr "fix/atomic-xp-update" \
    "fix(progression): use F() expressions for atomic XP increment to prevent lost updates" \
    "game/progression.py"

# PR 9: Username normalization
create_pr "fix/username-normalization" \
    "fix(forms): normalize username to lowercase during registration" \
    "game/forms.py"

# PR 10: Configurable Selenium timeout
create_pr "feat/configurable-selenium-timeout" \
    "feat(tests): make Selenium WebDriver timeout configurable via env var" \
    "game/selenium_tests/base.py"

# PR 11: Custom 404 page test
create_pr "test/custom-404-page" \
    "test(selenium): add test for custom 404 page rendering" \
    "game/selenium_tests/test_navigation.py"

# PR 12: check_username rate limit test
create_pr "test/check-username-rate-limit" \
    "test: add rate limit test for check_username endpoint" \
    "game/tests.py"

# PR 14: Preconnect for chess images
create_pr "perf/preconnect-chess-images" \
    "perf: add preconnect hint for chess piece image CDN" \
    "game/templates/game/landing.html"

# PR 15: Jest coverage thresholds
create_pr "feat/jest-coverage-thresholds" \
    "feat(testing): add minimum coverage thresholds to jest config" \
    "jest.config.cjs"

# PR 16: Discord link mismatch fix
create_pr "fix/discord-link-mismatch" \
    "fix: correct Discord invite link in CONTRIBUTING.md to match README" \
    "CONTRIBUTING.md"

# PR 18: Font fallback for badge generation
create_pr "fix/badge-font-fallback" \
    "fix(services): add cross-platform font fallback for badge generation" \
    "game/services.py"

echo ""
echo "=== 14 single-file PRs created ==="
echo "Now need to handle multi-file PRs manually:"
echo "  PR 2: engine.py path caching"
echo "  PR 5: toast.css + toast.js (already done above)"
echo "  PR 6: settings.py rate limiting"
echo "  PR 13: engine.py move history cap"
echo "  PR 17: settings.py engine timeout"
echo "  PR 19: landing.html (same as PR 14 - need different change)"
echo "  PR 20: settings.py (same as PR 6/17 - need different change)"
