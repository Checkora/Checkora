document.addEventListener("DOMContentLoaded", () => {
    const navToggle = document.getElementById("navToggle");
    const navLinks = document.getElementById("navLinks");
    const backdrop = document.getElementById("navBackdrop");

    if (!navToggle || !navLinks) return;

    function openMenu() {
        navLinks.classList.add("active");
        backdrop?.classList.add("active");
        navToggle.setAttribute("aria-expanded", "true");
    }

    function closeMenu() {
        navLinks.classList.remove("active");
        backdrop?.classList.remove("active");
        navToggle.setAttribute("aria-expanded", "false");
    }

    navToggle.addEventListener("click", () => {
        navLinks.classList.contains("active") ? closeMenu() : openMenu();
    });

    backdrop?.addEventListener("click", closeMenu);

    const navLinkElements = document.querySelectorAll(".nav-links a");
    navLinkElements.forEach((link) => {
        link.addEventListener("click", closeMenu);
    });

    window.addEventListener("resize", () => {
        if (window.innerWidth > 768) closeMenu();
    });
});