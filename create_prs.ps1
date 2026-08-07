$ErrorActionPreference = "Stop"
cd C:\Users\Abhinav\Checkora

# Ensure we're on main with no uncommitted changes
git checkout main 2>$null

# Helper function to create a PR branch
function Create-PR {
    param(
        [string]$BranchName,
        [string]$CommitMsg,
        [string[]]$Files
    )
    Write-Host "`n=== Creating PR: $BranchName ===" -ForegroundColor Cyan
    
    git checkout -b $BranchName main 2>$null
    
    # Apply changes from stash for specific files
    foreach ($file in $Files) {
        git checkout stash@{0} -- "$file" 2>$null
    }
    
    git add $Files
    git commit -m $CommitMsg 2>$null
    git push fork $BranchName 2>$null
    
    # Create PR via gh
    gh pr create --repo Checkora/Checkora --head Youngmaster0304:$BranchName --title $CommitMsg --body "Automated PR for Checkora contribution." 2>$null
    
    Write-Host "  Pushed and PR created for $BranchName" -ForegroundColor Green
}

# PR 1: C++ engine board validation
Create-PR "fix/cpp-engine-board-validation" "fix(engine): add board string input validation in loadBoard" @("game/engine/main.cpp")

# PR 2: Engine binary path caching
Create-PR "feat/engine-binary-path-caching" "perf(engine): cache resolved engine binary path to avoid repeated fs walks" @("game/engine.py")

# PR 3: Open Graph meta tags for board page
Create-PR "feat/og-tags-board-page" "feat: add Open Graph and Twitter Card meta tags to board page" @("game/templates/game/board.html")

# PR 4: prefers-reduced-motion for board
Create-PR "feat/reduced-motion-board" "feat(css): add prefers-reduced-motion support for board animations" @("game/static/game/css/board.css")

# PR 5: Toast stacking + ARIA
Create-PR "fix/toast-stacking-aria" "fix(toast): add stacking max-height, ARIA live region, and reduced-motion fallback" @("game/static/game/css/toast.css","game/static/game/js/toast.js")

# PR 6: Rate limiting config
Create-PR "feat/rate-limiting-config" "feat(settings): add configurable rate limiting and engine timeout settings" @("core/settings.py")

# PR 7: db_index on played_at
Create-PR "perf/db-index-played-at" "perf(models): add db_index on GameResult.played_at for query performance" @("game/models.py")

# PR 8: Atomic F() expressions for XP
Create-PR "fix/atomic-xp-update" "fix(progression): use F() expressions for atomic XP increment to prevent lost updates" @("game/progression.py")

# PR 9: Username normalization
Create-PR "fix/username-normalization" "fix(forms): normalize username to lowercase during registration" @("game/forms.py")

# PR 10: Configurable Selenium timeout
Create-PR "feat/configurable-selenium-timeout" "feat(tests): make Selenium WebDriver timeout configurable via env var" @("game/selenium_tests/base.py")

# PR 11: Custom 404 page test
Create-PR "test/custom-404-page" "test(selenium): add test for custom 404 page rendering" @("game/selenium_tests/test_navigation.py")

# PR 12: check_username rate limit test
Create-PR "test/check-username-rate-limit" "test: add rate limit test for check_username endpoint" @("game/tests.py")

# PR 13: Move history cap
Create-PR "fix/move-history-cap" "fix(engine): cap move_history at 300 entries to prevent session cookie overflow" @("game/engine.py")

# PR 14: Preconnect for chess images
Create-PR "perf/preconnect-chess-images" "perf: add preconnect hint for chess piece image CDN" @("game/templates/game/landing.html")

# PR 15: Jest coverage thresholds
Create-PR "feat/jest-coverage-thresholds" "feat(testing): add minimum coverage thresholds to jest config" @("jest.config.cjs")

# PR 16: Discord link mismatch fix
Create-PR "fix/discord-link-mismatch" "fix: correct Discord invite link in CONTRIBUTING.md to match README" @("CONTRIBUTING.md")

# PR 17: subprocess hard timeout kill
Create-PR "fix/engine-subprocess-hard-kill" "fix(engine): add hard timeout kill fallback for engine subprocess" @("game/engine.py")

# PR 18: Font fallback for badge generation
Create-PR "fix/badge-font-fallback" "fix(services): add cross-platform font fallback for badge generation" @("game/services.py")

# PR 19: Landing page Open Graph
Create-PR "feat/landing-og-tags" "feat: add Open Graph and Twitter Card meta tags to landing page" @("game/templates/game/landing.html")

# PR 20: Engine subprocess timeout setting
Create-PR "feat/engine-timeout-setting" "feat(settings): add ENGINE_SUBPROCESS_TIMEOUT and MAX_MOVE_HISTORY_LENGTH settings" @("core/settings.py")

# Return to main
git checkout main 2>$null
git stash pop 2>$null

Write-Host "`n=== All 20 PRs created! ===" -ForegroundColor Green
