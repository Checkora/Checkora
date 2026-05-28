/**
 * Shared dropdown toggle logic for the profile menu.
 * Used by both landing.html and board.html.
 */
document.addEventListener('DOMContentLoaded', () => {
    const dropdown = document.querySelector('.profile-dropdown');
    if (dropdown) {
        const btn = dropdown.querySelector('.profile-btn');
        const content = dropdown.querySelector('.dropdown-content');

        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            content.classList.toggle('show');
            btn.classList.toggle('active');
        });

        document.addEventListener('click', (e) => {
            if (!dropdown.contains(e.target)) {
                content.classList.remove('show');
                btn.classList.remove('active');
            }
        });
    }
});
