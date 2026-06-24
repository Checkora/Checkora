(function () {
    const safeLocalStorage = {
        get(key) {
            try {
                return window.localStorage.getItem(key);
            } catch (error) {
                return null;
            }
        },
        set(key, value) {
            try {
                window.localStorage.setItem(key, value);
            } catch (error) {
                // ignore restricted storage environments
            }
        }
    };

    // 1. Immediately apply the saved theme to prevent FOUC (visual flash)
    const storedTheme = safeLocalStorage.get("theme");
    const legacyTheme = safeLocalStorage.get("chessBoardTheme");
    const validStoredTheme = storedTheme === "light" || storedTheme === "dark" ? storedTheme : null;
    const savedTheme =
        validStoredTheme ||
        (legacyTheme === "light" || legacyTheme === "dark" ? legacyTheme : null) ||
        "dark";

    document.documentElement.setAttribute("data-theme", savedTheme);

    // 2. Set up event listeners for theme toggles when DOM is interactive/complete
    const initThemeToggle = () => {
        const toggles = document.querySelectorAll(".theme-toggle");

        const updateToggleState = (theme) => {
            toggles.forEach(toggle => {
                toggle.setAttribute("type", "button");
                toggle.setAttribute("aria-pressed", theme === "light" ? "true" : "false");
                toggle.setAttribute(
                    "aria-label",
                    theme === "light" ? "Switch to dark mode" : "Switch to light mode"
                );
                toggle.textContent = theme === "light" ? "☀️" : "🌙";
            });
        };

        // Initialize button states
        updateToggleState(savedTheme);

        // Bind event listeners to all toggles
        toggles.forEach(toggle => {
            toggle.onclick = () => {
                const currentTheme = document.documentElement.getAttribute("data-theme");
                const newTheme = currentTheme === "light" ? "dark" : "light";

                document.documentElement.setAttribute("data-theme", newTheme);
                safeLocalStorage.set("theme", newTheme);
                updateToggleState(newTheme);
            };
        });
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initThemeToggle);
    } else {
        initThemeToggle();
    }
})();
