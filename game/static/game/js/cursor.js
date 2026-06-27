(function() {
  const safeGet = function(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  };
  const safeSet = function(key, val) {
    try { window.localStorage.setItem(key, val); } catch (e) {}
  };
  var cursor = safeGet('selectedCursor') || 'default';
  if (cursor === 'glow') {
    document.documentElement.style.cursor = 'pointer';
    document.body.style.cursor = 'pointer';
  } else {
    document.documentElement.style.cursor = '';
    document.body.style.cursor = '';
  }
  window.__cursor = cursor;
  window.__setCursor = function(val) {
    cursor = val;
    safeSet('selectedCursor', val);
    window.__cursor = val;
    if (val === 'glow') {
      document.documentElement.style.cursor = 'pointer';
      document.body.style.cursor = 'pointer';
    } else {
      document.documentElement.style.cursor = '';
      document.body.style.cursor = '';
    }
  };
})();
