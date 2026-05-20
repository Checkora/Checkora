import { state } from './state.js';

const SOUND_BASE_URL = window.SOUND_BASE_URL || '/static/game/sounds/';

export const sounds = {
    move:    new Audio(`${SOUND_BASE_URL}move.wav`),
    capture: new Audio(`${SOUND_BASE_URL}capture.mp3`),
    check:   new Audio(`${SOUND_BASE_URL}check.wav`),
    draw:    new Audio(`${SOUND_BASE_URL}draw.mp3`),
};

export function playSound(data) {
    if (!state.soundEnabled || !data?.valid) return;

    let sound = sounds.move;
    if (['checkmate', 'stalemate', 'draw', 'timeout'].includes(data.game_status)) {
        sound = sounds.draw;
    } else if (data.game_status === 'check') {
        sound = sounds.check;
    } else if (data.captured || data.is_capture) {
        sound = sounds.capture;
    }

    sound.currentTime = 0;
    const p = sound.play();
    if (p?.catch) p.catch(() => {});
}

export function toggleMute() {
    state.soundEnabled = !state.soundEnabled;
    const muteBtn = document.getElementById('muteBtn');
    if (muteBtn) {
        muteBtn.textContent = state.soundEnabled ? '🔊 Sound On' : '🔇 Muted';
        muteBtn.setAttribute('aria-pressed', String(state.soundEnabled));
    }
}