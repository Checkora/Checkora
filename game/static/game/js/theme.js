document.addEventListener("DOMContentLoaded", () => {
    const storedTheme = localStorage.getItem("theme");
    const legacyTheme = localStorage.getItem("chessBoardTheme");
    const validStoredTheme = storedTheme === "light" || storedTheme === "dark" ? storedTheme : null;
    const savedTheme =
        validStoredTheme ||
        (legacyTheme === "light" || legacyTheme === "dark" ? legacyTheme : null) ||
        "dark";

    document.documentElement.setAttribute(
        "data-theme",
        savedTheme
    );

    const toggle = document.getElementById("themeToggle");

    if (toggle) {
        toggle.textContent =
            savedTheme === "light" ? "☀️" : "🌙";

        toggle.addEventListener("click", () => {
            const current =
                document.documentElement.getAttribute("data-theme");

            const next =
                current === "light" ? "dark" : "light";

            document.documentElement.setAttribute(
                "data-theme",
                next
            );

            localStorage.setItem("theme", next);

            toggle.textContent =
                next === "light" ? "☀️" : "🌙";
        });
    }
});