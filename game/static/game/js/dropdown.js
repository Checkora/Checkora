document.addEventListener('DOMContentLoaded', function() {
    const dropdown = document.querySelector('.profile-dropdown');
    if (!dropdown) return;

    const btn = dropdown.querySelector('.profile-btn');
    const content = dropdown.querySelector('.dropdown-content');

    if (btn && content) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            dropdown.classList.toggle('active');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!dropdown.contains(e.target)) {
                dropdown.classList.remove('active');
            }
        });

        // Close on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                dropdown.classList.remove('active');
            }
        });

        // Accessibility: close when focus moves outside the dropdown
        dropdown.addEventListener('focusout', function(e) {
            // Use setTimeout to allow focus to move to the new element
            setTimeout(() => {
                if (!dropdown.contains(document.activeElement)) {
                    dropdown.classList.remove('active');
                }
            }, 10);
        });
    }
});
