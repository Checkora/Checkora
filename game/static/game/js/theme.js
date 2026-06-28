// 1. Theme detection and attribute setting run immediately at the top-level.
// This prevents layout flashes and transition animations on initial page load.
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

const storedTheme = safeLocalStorage.get("theme");
const legacyTheme = safeLocalStorage.get("chessBoardTheme");
const validStoredTheme = storedTheme === "light" || storedTheme === "dark" ? storedTheme : null;
const savedTheme =
    validStoredTheme ||
    (legacyTheme === "light" || legacyTheme === "dark" ? legacyTheme : null) ||
    "dark";

document.documentElement.setAttribute(
    "data-theme",
    savedTheme
);

// 2. DOM-dependent logic runs after content is loaded.
        document.addEventListener("DOMContentLoaded", () => {
            const toggles = document.querySelectorAll(".theme-toggle");

            const updateToggleState = (theme) => {
            toggles.forEach((toggle) => {
                toggle.setAttribute("type", "button");
                toggle.setAttribute(
                    "aria-pressed",
                    theme === "light" ? "true" : "false"
                );
                toggle.setAttribute(
                    "aria-label",
                    theme === "light"
                        ? "Switch to dark mode"
                        : "Switch to light mode"
                );
                toggle.textContent = theme === "light" ? "☀️" : "🌙";
            });
        };

    // Helper to safely trigger toast notifications, dynamically loading
    // toast.js and toast.css on demand if they aren't statically loaded on the page.
    const showThemeToast = (message, type = "info") => {
        if (typeof window.showToast === "function") {
            window.showToast(message, type);
        } else {
            // Dynamically load toast.css if not present
            if (!document.getElementById("toast-css-dynamic")) {
                const link = document.createElement("link");
                link.id = "toast-css-dynamic";
                link.rel = "stylesheet";
                link.href = "/static/game/css/toast.css";
                document.head.appendChild(link);
            }
            // Dynamically load toast.js if not present
            const existingScript = document.getElementById("toast-js-dynamic");
            if (!existingScript) {
                const script = document.createElement("script");
                script.id = "toast-js-dynamic";
                script.src = "/static/game/js/toast.js";
                script.onload = () => {
                    if (typeof window.showToast === "function") {
                        window.showToast(message, type);
                    }
                };
                document.body.appendChild(script);
            } else {
                // If script exists but window.showToast is not yet defined, it means the script is currently loading.
                // We attach the callback to the existing script's load event.
                existingScript.addEventListener("load", () => {
                    if (typeof window.showToast === "function") {
                        window.showToast(message, type);
                    }
                });
            }
        }
    };

    updateToggleState(savedTheme);

    let transitionTimeout = null;

    toggles.forEach((toggle) => {
    toggle.addEventListener("click", () => {
            const currentTheme = document.documentElement.getAttribute("data-theme");
            const newTheme = currentTheme === "light" ? "dark" : "light";

            // Clear any active transition timeout to handle rapid toggles
            if (transitionTimeout) {
                clearTimeout(transitionTimeout);
            }

            // Temporarily enable theme transitions
            document.documentElement.classList.add("theme-transition");
            document.documentElement.setAttribute("data-theme", newTheme);
            safeLocalStorage.set("theme", newTheme);
            updateToggleState(newTheme);

            // Trigger the toast notification
            showThemeToast(`Switched to ${newTheme === "light" ? "Light" : "Dark"} Mode`, "info");

            // Remove the class after the transition finishes (0.3s)
            transitionTimeout = setTimeout(() => {
                document.documentElement.classList.remove("theme-transition");
                transitionTimeout = null;
            }, 300);
        });
    }
)});
