function csrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

async function parseJson(response) {
    const text = await response.text();
    return text ? JSON.parse(text) : {};
}

async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await parseJson(response);

    if (!response.ok) {
        const message = data.message || `Request failed with status ${response.status}.`;
        throw Object.assign(new Error(message), { data, response });
    }

    return data;
}

function getJson(url) {
    return requestJson(url);
}

function postJson(url, body = {}) {
    return requestJson(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken(),
        },
        body: JSON.stringify(body),
    });
}

export const gameApi = {
    state: () => getJson('/api/state/'),
    validMoves(row, col) {
        const query = new URLSearchParams({ row, col });
        return getJson(`/api/valid-moves/?${query}`);
    },
    move: payload => postJson('/api/move/', payload),
    newGame: payload => postJson('/api/new-game/', payload),
    pause: payload => postJson('/api/pause/', payload),
    aiMove: () => postJson('/api/ai-move/'),
    draw: payload => postJson('/api/draw/', payload),
    resign: () => postJson('/api/resign/'),
};
