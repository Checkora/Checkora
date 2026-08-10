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

// ── Random Chess Quote (Hero → Platform Capabilities) ──
document.addEventListener("DOMContentLoaded", () => {
    const quoteTextEl = document.getElementById("chessQuoteText");
    const quoteAuthorEl = document.getElementById("chessQuoteAuthor");

    if (!quoteTextEl || !quoteAuthorEl) return;

    const quotes = [
        { text: "Every chess master was once a beginner.", author: "Irving Chernev" },
        { text: "Chess is the gymnasium of the mind.", author: "Blaise Pascal" },
        { text: "Chess is life in miniature.", author: "Garry Kasparov" },
        { text: "When you see a good move, look for a better one.", author: "Emanuel Lasker" },
        { text: "Tactics flow from a superior position.", author: "Bobby Fischer" },
        { text: "The blunders are all there on the board, waiting to be made.", author: "Savielly Tartakower" },
        { text: "A good player is always lucky.", author: "Jose Raul Capablanca" },
        { text: "In life, as in chess, forethought wins.", author: "Charles Buxton" },
        { text: "Chess is beautiful enough to waste your life for.", author: "Hans Ree" },
        { text: "You may learn much more from a game you lose than from a game you win.", author: "Jose Raul Capablanca" },
        { text: "Chess, like love, like music, has the power to make people happy.", author: "Siegbert Tarrasch" },
        { text: "Even a poor plan is better than no plan at all.", author: "Mikhail Chigorin" }
    ];

    const randomQuote = quotes[Math.floor(Math.random() * quotes.length)];

    quoteTextEl.textContent = randomQuote.text;
    quoteAuthorEl.textContent = randomQuote.author;
});