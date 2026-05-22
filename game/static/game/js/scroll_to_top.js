(function () {
  const SHOW_AFTER_PX = 320;

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'scroll-top-button';
  button.setAttribute('aria-label', 'Scroll back to top');
  button.textContent = '↑';
  document.body.appendChild(button);

  const updateVisibility = () => {
    button.classList.toggle('is-visible', window.scrollY > SHOW_AFTER_PX);
  };

  button.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  window.addEventListener('scroll', updateVisibility, { passive: true });
  updateVisibility();
})();
