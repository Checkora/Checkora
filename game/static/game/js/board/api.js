/**
 * board/api.js — CSRF, fetch wrappers, button loading helper, reconnect logic
 *
 * Extracted from board.js: csrf, get, post, withLoading, handleReconnect
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  function csrf() {
    if (typeof document === 'undefined') return '';
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input?.value) {
      return input.value;
    }
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  async function get(url) {
    const res = await fetch(url);
    if (res && res.ok !== undefined && !res.ok) throw new Error(`GET ${url} failed: ${res.status}`);
    return res.json();
  }

  async function post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf()
      },
      body: JSON.stringify(body)
    });
    if (res && res.ok !== undefined && !res.ok) throw new Error(`POST ${url} failed: ${res.status}`);
    return res.json();
  }

  async function withLoading(btn, asyncFn) {
    if (!btn || btn.classList.contains('is-loading')) {
      return asyncFn ? asyncFn() : undefined;
    }
    btn.classList.add('is-loading');
    btn.disabled = true;
    try {
      return await asyncFn();
    } finally {
      btn.classList.remove('is-loading');
      btn.disabled = false;
    }
  }

  let reconnecting = false;
  async function handleReconnect() {
    if (reconnecting) return;
    reconnecting = true;
    if (CB.showStatus) CB.showStatus('Reconnecting...', false);
    let retries = 0;
    let success = false;
    while (retries < 3 && !success) {
      try {
        await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, retries)));
        if (!CB.loadGame) throw new Error('loadGame not available');
        await CB.loadGame();
        success = true;
      } catch (err) {
        retries++;
      }
    }

    if (success) {
      if (CB.showStatus) CB.showStatus('Connection restored', false);
      setTimeout(() => {
        if (CB.showStatus) CB.showStatus('', false);
      }, 2000);
    } else {
      if (CB.showStatus) CB.showStatus('Unable to reconnect. Please refresh.', true);
    }
    reconnecting = false;
  }

  CB.csrf = csrf;
  CB.get = get;
  CB.post = post;
  CB.withLoading = withLoading;
  CB.handleReconnect = handleReconnect;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      csrf: csrf,
      get: get,
      post: post,
      withLoading: withLoading,
      handleReconnect: handleReconnect
    };
  }
})();
