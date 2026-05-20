export function initThemeSwitcher() {
    const themeBtns    = document.querySelectorAll('.theme-btn');
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'classic';
    document.documentElement.setAttribute('data-theme', currentTheme);

    themeBtns.forEach(btn => {
        if (btn.dataset.theme === currentTheme) {
            btn.classList.add('active');
            btn.setAttribute('aria-pressed', 'true');
        }
        btn.onclick = () => {
            const theme = btn.dataset.theme;
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('chessBoardTheme', theme);
            themeBtns.forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-pressed', 'false');
            });
            btn.classList.add('active');
            btn.setAttribute('aria-pressed', 'true');
        };
    });
}