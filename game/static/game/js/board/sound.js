/**
 * board/sound.js — Audio effects, mute toggle, game over sounds
 *
 * Extracted from board.js lines 557–660: sounds, playSound, toggleMute, playGameOverSound
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  const baseUrl = typeof SOUND_BASE_URL !== 'undefined' ? SOUND_BASE_URL : '/static/game/sounds/';
  const AudioConstructor = typeof Audio !== 'undefined' ? Audio : class {
    constructor() {}
    play() { return Promise.resolve(); }
  };

  const sounds = {
    move: new AudioConstructor(`${baseUrl}move.wav`),
    capture: new AudioConstructor(`${baseUrl}capture.mp3`),
    check: new AudioConstructor(`${baseUrl}check.wav`),
    draw: new AudioConstructor(`${baseUrl}draw.mp3`),
    win: new AudioConstructor(`${baseUrl}win.mp3`),
    loss: new AudioConstructor(`${baseUrl}loss.mp3`),
    gameDraw: new AudioConstructor(`${baseUrl}draw_end.mp3`),
    timeout: new AudioConstructor(`${baseUrl}timeout.mp3`),
  };

  if (typeof localStorage !== 'undefined') {
    try {
      const savedSound = localStorage.getItem('chessSoundEnabled');
      if (savedSound !== null) {
        CB.S.soundEnabled = (savedSound === 'true');
      }
    } catch (e) {
      console.error("Failed to load sound settings", e);
    }
  }

  function playSound(data) {
    if (!CB.S.soundEnabled || !data?.valid) return;

    let sound = sounds.move;
    if (['checkmate', 'stalemate', 'draw', 'timeout'].includes(data.game_status)) {
      sound = sounds.draw;
    } else if (data.game_status === 'check') {
      sound = sounds.check;
    } else if (data.captured || data.is_capture) {
      sound = sounds.capture;
    }

    sound.currentTime = 0;
    const playback = sound.play();
    if (playback?.catch) playback.catch(() => {});
  }

  function toggleMute() {
    CB.S.soundEnabled = !CB.S.soundEnabled;
    if (typeof localStorage !== 'undefined') {
      try {
        localStorage.setItem('chessSoundEnabled', String(CB.S.soundEnabled));
      } catch (e) {
        console.error("Failed to save sound settings", e);
      }
    }
    if (CB.DOM.muteBtn) {
      CB.DOM.muteBtn.textContent = CB.S.soundEnabled ? '🔊 Sound On' : '🔇 Muted';
      CB.DOM.muteBtn.setAttribute('aria-pressed', String(CB.S.soundEnabled));
    }
  }

  function playGameOverSound(reason, resultState) {
    if (!CB.S.soundEnabled) return;

    let sound = null;
    if (reason === 'stalemate' || reason === 'draw') {
      sound = sounds.gameDraw;
    } else if (reason === 'timeout') {
      sound = sounds.timeout;
    } else if (reason === 'checkmate' || reason === 'resign') {
      if (resultState === 'defeat') {
        sound = sounds.loss;
      } else {
        sound = sounds.win;
      }
    }

    if (sound) {
      sound.currentTime = 0;
      sound.play().catch((e) => console.log('Sound play error:', e));
    }
  }

  CB.sounds = sounds;
  CB.playSound = playSound;
  CB.toggleMute = toggleMute;
  CB.playGameOverSound = playGameOverSound;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      sounds: sounds,
      playSound: playSound,
      toggleMute: toggleMute,
      playGameOverSound: playGameOverSound
    };
  }
})();
