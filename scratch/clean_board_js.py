import os

file_path = "game/static/game/js/board.js"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Variables
content = content.replace("let paused = false;", "")
content = content.replace("const pauseBtn = document.getElementById('pauseBtn');", "")
content = content.replace("let wasPaused = false;", "")

# 2. Variable assignments
content = content.replace("paused = data.paused;", "")
content = content.replace("paused = true;", "")
content = content.replace("paused = false;", "")
content = content.replace("paused = d.paused;", "")

content = content.replace("if (pauseBtn)  pauseBtn.style.display  = 'block';", "")
content = content.replace("if (pauseBtn) pauseBtn.style.display = 'none';", "")
content = content.replace("if (pauseBtn) pauseBtn.style.display = '';", "")
content = content.replace("updatePauseUI();", "")

# 3. Conditionals
content = content.replace("if (paused || gameOver) return e.preventDefault();", "if (gameOver) return e.preventDefault();")
content = content.replace("if (!p || paused || gameOver) return;", "if (!p || gameOver) return;")
content = content.replace("if (paused || gameOver) return;", "if (gameOver) return;")
content = content.replace("if (paused || gameOver || gameMode !== 'pvp') return;", "if (gameOver || gameMode !== 'pvp') return;")
content = content.replace("if (!piece || paused || gameOver) return;", "if (!piece || gameOver) return;")
content = content.replace("if (paused || gameOver) {", "if (gameOver) {")

content = content.replace("if (paused) return;", "")

content = content.replace("await pauseGame();", "")

# 4. Functions
pause_func = """            async function pauseGame() {
                if (paused) return;
                const d = await post('/api/pause/', { pause: true });
                paused = d.paused;
                whiteTime = d.white_time;
                blackTime = d.black_time;
                updatePauseUI();
                renderClocks();
            }"""
content = content.replace(pause_func, "")

resume_func = """            async function resumeGame() {
                try {
                    const d = await post('/api/pause/', { pause: false });

                    paused = false;

                    if (d.white_time !== undefined) {
                        whiteTime = d.white_time;
                    }

                    if (d.black_time !== undefined) {
                        blackTime = d.black_time;
                    }

                    updatePauseUI();
                    renderClocks();

                    clearInterval(timerInterval);
                    startTimer();

                    boardEl.classList.remove('paused');

                    queueAIMoveIfNeeded();

                } catch (e) {
                    console.error("Resume failed", e);
                }
            }"""
content = content.replace(resume_func, "")

# Upstream updated updatePauseUI
update_ui_func_upstream = """            function updatePauseUI() {
                pauseBtn.textContent = paused ? 'Resume' : 'Pause';
                pauseBtn.classList.toggle('paused', paused);
                boardEl.classList.toggle('paused', paused);
                if (paused) {
                    boardEl.setAttribute('aria-label', 'Game paused. Click board or press P to resume.');
                    boardEl.style.cursor = 'pointer';
                    boardEl.style.pointerEvents = 'auto';
                } else {
                    boardEl.removeAttribute('aria-label');
                    boardEl.style.cursor = '';
                    boardEl.style.pointerEvents = '';
                }
            }"""
content = content.replace(update_ui_func_upstream, "")

# 5. Remaining wasPaused logic
was_paused_1 = """    wasPaused = paused;

    if (wasPaused) {
        boardEl.classList.remove('paused');
    }"""
content = content.replace(was_paused_1, "")

content = content.replace("if (wasPaused) boardEl.classList.add('paused');", "")

was_paused_2 = """                if (wasPaused) {
                    boardEl.classList.add('paused');
                }"""
content = content.replace(was_paused_2, "")

# 6. Event Listeners
content = content.replace("if (pauseBtn) pauseBtn.onclick = () => paused ? resumeGame() : pauseGame();", "")

key_p = """                } else if (key === 'p' && pauseBtn && pauseBtn.style.display !== 'none') {
                    e.preventDefault();
                    pauseBtn.click();"""
content = content.replace(key_p, "")

before_unload = """           // Custom leave confirmation modal instead of browser default dialog
            if (!navigator.webdriver) {
                window.addEventListener('beforeunload', (e) => {
               if (!paused) {
                    const blob = new Blob([JSON.stringify({ pause: true })], { type: 'application/json' });
                    navigator.sendBeacon('/api/pause/', blob);
                   }
                });
            }"""
content = content.replace(before_unload, """           // Custom leave confirmation modal instead of browser default dialog
            if (!navigator.webdriver) {
                window.addEventListener('beforeunload', (e) => {
                });
            }""")

visibility_change = """    document.addEventListener('visibilitychange', async() => {
        if (document.hidden) {
            pauseGame().catch(() => {});
        } else {
            await handleReconnect();
        }
    });"""
content = content.replace(visibility_change, """    document.addEventListener('visibilitychange', async() => {
        if (!document.hidden) {
            await handleReconnect();
        }
    });""")

asset_warning_1 = """                // 1. Pause the timer while the alert is open
                if (!paused && typeof pauseGame === 'function') {
                    pauseGame().catch(() => {}); // Catch prevents crash if backend hasn't initialized
                }"""
content = content.replace(asset_warning_1, "")

asset_warning_2 = """                        // 2. Set a memory flag to bypass the main menu on reload
                        sessionStorage.setItem('checkoraAutoResume', 'true');"""
content = content.replace(asset_warning_2, "                        // 2. Reload")

asset_warning_3 = """                // 3. Resume the timer if they click Close
                if (noBtn) {
                    noBtn.textContent = 'Close';
                    const defaultClose = noBtn.onclick; 
                    noBtn.onclick = () => {
                        if (defaultClose) defaultClose();
                        if (paused && typeof resumeGame === 'function') {
                            resumeGame().catch(() => {});
                        }
                    };
                }"""
content = content.replace(asset_warning_3, """                // 3. Resume the timer if they click Close
                if (noBtn) {
                    noBtn.textContent = 'Close';
                    const defaultClose = noBtn.onclick; 
                    noBtn.onclick = () => {
                        if (defaultClose) defaultClose();
                    };
                }""")

# Upstream added event listener
resume_click = """            // Resume game by clicking the paused board overlay
            boardEl.addEventListener('click', async () => {
                if (!paused) return;
                if (drawOverlay.classList.contains('active')) return;
                if (confirmOverlay.classList.contains('active')) return;
                if (gameOverOverlay.classList.contains('active')) return;
                await resumeGame();
            });"""
content = content.replace(resume_click, "")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
