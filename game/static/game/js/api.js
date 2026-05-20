// ============================================================
// API HELPERS
// ============================================================
export function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
}

export async function get(url) {
    return (await fetch(url)).json();
}

export async function post(url, body) {
    return (await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf(),
        },
        body: JSON.stringify(body),
    })).json();
}