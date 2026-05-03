const COLORS = ['w', 'b'];
const TYPES = ['k', 'q', 'r', 'b', 'n', 'p'];
const BASE_URL = 'https://images.chesscomfiles.com/chess-themes/pieces/neo/150';

export const PIECE_IMAGES = Object.fromEntries(
    COLORS.flatMap(color => TYPES.map(type => [`${color}${type}`, `${BASE_URL}/${color}${type}.png`]))
);

export const PROMOTION_CHOICES = [
    { key: 'q', label: 'Queen' },
    { key: 'r', label: 'Rook' },
    { key: 'b', label: 'Bishop' },
    { key: 'n', label: 'Knight' },
];

export function pieceKey(piece) {
    if (!piece) return null;
    return `${piece === piece.toUpperCase() ? 'w' : 'b'}${piece.toLowerCase()}`;
}

export function pieceColor(piece) {
    if (!piece) return null;
    return piece === piece.toUpperCase() ? 'white' : 'black';
}
