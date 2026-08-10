const {
    initializeForumTabs,
} = require("./game/static/game/js/forum");

function createForumDOM() {
    document.body.innerHTML = `
        <button class="forum-tab active" data-tab="all">All</button>
        <button class="forum-tab" data-tab="your">Your</button>
        <button class="forum-tab" data-tab="bookmarked">Bookmarked</button>

        <div id="tab-all" class="forum-tab-panel active"></div>
        <div id="tab-your" class="forum-tab-panel"></div>
        <div id="tab-bookmarked" class="forum-tab-panel"></div>
    `;
}

beforeEach(() => {
    createForumDOM();
});

test("restores the all tab from the URL hash", () => {
    window.location.hash = "#tab-all";

    initializeForumTabs();

    expect(
        document.querySelector('[data-tab="all"]').classList.contains("active")
    ).toBe(true);
});

test("restores the your tab from the URL hash", () => {
    window.location.hash = "#tab-your";

    initializeForumTabs();

    expect(
        document.querySelector('[data-tab="your"]').classList.contains("active")
    ).toBe(true);
});

test("restores the bookmarked tab from the URL hash", () => {
    window.location.hash = "#tab-bookmarked";

    initializeForumTabs();

    expect(
        document
            .querySelector('[data-tab="bookmarked"]')
            .classList.contains("active")
    ).toBe(true);
});