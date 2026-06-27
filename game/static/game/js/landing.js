document.addEventListener("DOMContentLoaded", () => {
    const navToggle = document.getElementById("navToggle");
    const navLinks = document.getElementById("navLinks");
    const backdrop = document.getElementById("navBackdrop");

    // Exit if required elements are missing
    if (!navToggle || !navLinks) return;

    function openMenu() {
        navLinks.classList.add("active");

        if (backdrop) {
            backdrop.classList.add("active");
        }

        navToggle.setAttribute("aria-expanded", "true");
    }

    function closeMenu() {
        navLinks.classList.remove("active");

        if (backdrop) {
            backdrop.classList.remove("active");
        }

        navToggle.setAttribute("aria-expanded", "false");
    }

    function toggleMenu() {
        if (navLinks.classList.contains("active")) {
            closeMenu();
        } else {
            openMenu();
        }
    }

    // Toggle menu
    navToggle.addEventListener("click", toggleMenu);

    // Close when backdrop is clicked
    if (backdrop) {
        backdrop.addEventListener("click", closeMenu);
    }

    // Close when a navigation link is clicked
    document.querySelectorAll(".nav-links a").forEach((link) => {
        link.addEventListener("click", closeMenu);
    });

    // Close menu when switching back to desktop
    window.addEventListener("resize", () => {
        if (window.innerWidth > 768) {
            closeMenu();
        }
    });
});