function activateTab(tabId) {
    const tabBtn = document.querySelector(`.forum-tab[data-tab="${tabId}"]`);
    const panel = document.getElementById(`tab-${tabId}`);

    if (!tabBtn || !panel) return;

    document.querySelectorAll(".forum-tab").forEach((tab) => {
        tab.classList.remove("active");
    });

    document.querySelectorAll(".forum-tab-panel").forEach((tabPanel) => {
        tabPanel.classList.remove("active");
    });

    tabBtn.classList.add("active");
    panel.classList.add("active");
}

function restoreTabFromHash() {
    const hashTab = window.location.hash.replace(/^#tab-/, "");

    if (hashTab) {
        activateTab(hashTab);
    }
}

function initializeForumTabs() {
    restoreTabFromHash();

    document.querySelectorAll(".forum-tab").forEach((tab) => {
        tab.addEventListener("click", () => {
            const target = tab.dataset.tab;
            activateTab(target);
            window.location.hash = `tab-${target}`;
        });
    });
}

window.addEventListener("DOMContentLoaded", initializeForumTabs);
window.addEventListener("hashchange", restoreTabFromHash);

if (typeof module !== "undefined") {
    module.exports = {
        activateTab,
        restoreTabFromHash,
        initializeForumTabs,
    };
}