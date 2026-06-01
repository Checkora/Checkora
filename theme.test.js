/**
 * @jest-environment jsdom
 */

describe('CheckoraTheme', () => {
    beforeEach(() => {
        document.documentElement.removeAttribute('data-color-scheme');
        localStorage.clear();
        jest.resetModules();
        document.body.innerHTML =
            '<button type="button" data-color-scheme-toggle id="colorSchemeToggle"></button>';
    });

    test('defaults to dark when storage is empty', () => {
        require('./game/static/game/js/theme.js');
        expect(document.documentElement.getAttribute('data-color-scheme')).toBeNull();
        expect(window.CheckoraTheme.get()).toBe('dark');
    });

    test('apply persists light mode', () => {
        require('./game/static/game/js/theme.js');
        window.CheckoraTheme.apply('light');
        expect(document.documentElement.getAttribute('data-color-scheme')).toBe('light');
        expect(localStorage.getItem('checkoraColorScheme')).toBe('light');
    });

    test('toggle switches between light and dark', () => {
        require('./game/static/game/js/theme.js');
        window.CheckoraTheme.apply('dark');
        window.CheckoraTheme.toggle();
        expect(document.documentElement.getAttribute('data-color-scheme')).toBe('light');
        window.CheckoraTheme.toggle();
        expect(document.documentElement.getAttribute('data-color-scheme')).toBe('dark');
    });
});
