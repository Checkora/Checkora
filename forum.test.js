const {
    initializeForumTabs,
} = require("./game/static/game/js/forum");

function createForumDOM() {
    document.body.innerHTML = `
        <button class="forum-tab active" data-tab="all" role="tab" aria-selected="true">All</button>
        <button class="forum-tab" data-tab="your" role="tab" aria-selected="false">Your</button>
        <button class="forum-tab" data-tab="bookmarked" role="tab" aria-selected="false">Bookmarked</button>

        <div id="tab-all" class="forum-tab-panel active"></div>
        <div id="tab-your" class="forum-tab-panel"></div>
        <div id="tab-bookmarked" class="forum-tab-panel"></div>
    `;
}

// aria-selected of the three tabs, in the order all, your, bookmarked.
function selectedTabs() {
    return ["all", "your", "bookmarked"].map((name) =>
        document.querySelector(`[data-tab="${name}"]`).getAttribute("aria-selected")
    );
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
    expect(selectedTabs()).toEqual(["true", "false", "false"]);
});

test("restores the your tab from the URL hash", () => {
    window.location.hash = "#tab-your";

    initializeForumTabs();

    expect(
        document.querySelector('[data-tab="your"]').classList.contains("active")
    ).toBe(true);
    expect(selectedTabs()).toEqual(["false", "true", "false"]);
});

test("restores the bookmarked tab from the URL hash", () => {
    window.location.hash = "#tab-bookmarked";

    initializeForumTabs();

    expect(
        document
            .querySelector('[data-tab="bookmarked"]')
            .classList.contains("active")
    ).toBe(true);
    expect(selectedTabs()).toEqual(["false", "false", "true"]);
});

test("a click selects the tab for screen readers as well as for the eye", () => {
    window.location.hash = "#tab-all";

    initializeForumTabs();
    document.querySelector('[data-tab="bookmarked"]').click();

    expect(selectedTabs()).toEqual(["false", "false", "true"]);
    expect(
        document.getElementById("tab-bookmarked").classList.contains("active")
    ).toBe(true);

    document.querySelector('[data-tab="all"]').click();

    expect(selectedTabs()).toEqual(["true", "false", "false"]);
});
