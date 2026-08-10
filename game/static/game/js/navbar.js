function initNavbar() {
    const navToggle = document.getElementById("navToggle");
    const navLinks = document.getElementById("navLinks");
    const backdrop = document.getElementById("navBackdrop");

    if (!navToggle || !navLinks) return;

    function openMenu() {
        navLinks.classList.add("active");
        if (backdrop) backdrop.classList.add("active");
        navToggle.setAttribute("aria-expanded", "true");
    }

    function closeMenu() {
        navLinks.classList.remove("active");
        if (backdrop) backdrop.classList.remove("active");
        navToggle.setAttribute("aria-expanded", "false");
    }

    navToggle.addEventListener("click", (e) => {
        e.stopPropagation();
        navLinks.classList.contains("active") ? closeMenu() : openMenu();
    });

    if (backdrop) {
        backdrop.addEventListener("click", closeMenu);
    }

    const navLinkElements = navLinks.querySelectorAll("a");
    navLinkElements.forEach((link) => {
        link.addEventListener("click", closeMenu);
    });

    window.addEventListener("resize", () => {
        if (window.innerWidth > 768) closeMenu();
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initNavbar);
} else {
    initNavbar();
}
