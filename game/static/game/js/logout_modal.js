document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('logoutConfirmModal');
  if (!modal) {
    return;
  }

  const logoutForms = document.querySelectorAll('[data-logout-confirm="true"]');
  const confirmButton = modal.querySelector('[data-logout-confirm]');
  const cancelButtons = modal.querySelectorAll('[data-logout-cancel]');
  let activeForm = null;

  const closeModal = () => {
    modal.hidden = true;
    activeForm = null;
  };

  logoutForms.forEach((form) => {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      activeForm = form;
      modal.hidden = false;
    });
  });

  cancelButtons.forEach((button) => {
    button.addEventListener('click', closeModal);
  });

  confirmButton?.addEventListener('click', () => {
    if (activeForm) {
      activeForm.submit();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.hidden) {
      closeModal();
    }
  });
});
