/**
 * board/promo.js — Pawn promotion dialog & handling
 *
 * Extracted from board.js: showPromoModal, hidePromoModal, onPromoChoice
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  function showPromoModal(color) {
    if (!CB.DOM.promoChoices || !CB.DOM.promoOverlay) return;
    const prefix = color === 'white' ? 'w' : 'b';
    const pieces = [
      { key: 'q', label: 'Queen' },
      { key: 'r', label: 'Rook' },
      { key: 'b', label: 'Bishop' },
      { key: 'n', label: 'Knight' },
    ];
    CB.DOM.promoChoices.innerHTML = '';
    pieces.forEach(({ key }) => {
      const btn = document.createElement('button');
      btn.className = 'promo-btn';
      const img = document.createElement('img');
      img.src = CB.PIECE_IMG[prefix + key];
      btn.appendChild(img);
      btn.onclick = () => onPromoChoice(key);
      CB.DOM.promoChoices.appendChild(btn);
    });
    CB.DOM.promoOverlay.classList.add('active');
  }

  function hidePromoModal() {
    if (!CB.DOM.promoOverlay) return;
    CB.DOM.promoOverlay.classList.remove('active');
    CB.S.pendingPromo = null;
  }

  async function onPromoChoice(choice) {
    if (!CB.S.pendingPromo) return;
    const { fr, fc, tr, tc } = CB.S.pendingPromo;
    hidePromoModal();
    if (CB.executeMove) await CB.executeMove(fr, fc, tr, tc, choice, true);
  }

  CB.showPromoModal = showPromoModal;
  CB.hidePromoModal = hidePromoModal;
  CB.onPromoChoice = onPromoChoice;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      showPromoModal: showPromoModal,
      hidePromoModal: hidePromoModal,
      onPromoChoice: onPromoChoice
    };
  }
})();
