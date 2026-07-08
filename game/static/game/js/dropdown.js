document.addEventListener('DOMContentLoaded', function () {
    
    const dropdown = document.querySelector('.profile-dropdown');
    if (!dropdown) return;

    const btn = dropdown.querySelector('.profile-btn');
    const content = dropdown.querySelector('.dropdown-content');
    function closeDropdown() {
        dropdown.classList.remove('active');
        btn.setAttribute('aria-expanded', 'false');
    }

    if (btn && content) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const isActive = dropdown.classList.toggle('active');
            btn.setAttribute('aria-expanded', isActive ? 'true' : 'false');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!dropdown.contains(e.target)) {
                closeDropdown();
            }
        });

        // Close on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeDropdown();
            }
        });

        // Accessibility: close when focus moves outside the dropdown
        dropdown.addEventListener('focusout', function(e) {
            // Use setTimeout to allow focus to move to the new element
            setTimeout(() => {
                if (!dropdown.contains(document.activeElement)) {
                    closeDropdown();
                }
            }, 10);
        });
        window.addEventListener(
        'scroll',
        closeDropdown,
        { passive: true }
    );
    }
});
