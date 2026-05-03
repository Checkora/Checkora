/**
 * Checkora Chess Engine
 *
 * Validates chess moves and computes legal move sets.
 * Communicates with the Django backend via stdin/stdout.
 *
 * Protocol:
 * VALIDATE <board64> <turn> <fr> <fc> <tr> <tc>
 * -> VALID | INVALID <reason>
 *
 * MOVES <board64> <turn> <row> <col>
 * -> MOVES [<row> <col> <is_capture> <is_promotion> ...]
 *
 * ATTACKED <board64> <attackerColor> <row> <col>
 * -> YES | NO
 *
 * PROMOTE <board64> <turn> <fr> <fc> <tr> <tc> <promoPiece>
 * -> PROMOTE <newBoard64>
 *    Validates the promotion move, applies it to the board,
 *    and returns the resulting 64-char board string.
 *    Returns INVALID if the move is not a legal promotion.
 */

#include <iostream>
#include <string>
#include <cmath>
#include <cctype>
#include <vector>
#include <climits>
#include <algorithm>
#include <bits/stdc++.h>

using namespace std;

// ============================================================
//  Board representation
// ============================================================

char board[8][8];
bool W_K_CASTLE = false;
bool W_Q_CASTLE = false;
bool B_K_CASTLE = false;
bool B_Q_CASTLE = false;
int EN_PASSANT_R = -1;
int EN_PASSANT_C = -1;

void loadBoard(const string &s) {
    for (int i = 0; i < 64 && i < (int)s.length(); i++) {
        board[i / 8][i % 8] = s[i];
    }
}

void loadCastlingRights(const string &rightsStr) {
    W_K_CASTLE = W_Q_CASTLE = B_K_CASTLE = B_Q_CASTLE = false;
    for (char c : rightsStr) {
        if (c == 'K') W_K_CASTLE = true;
        else if (c == 'Q') W_Q_CASTLE = true;
        else if (c == 'k') B_K_CASTLE = true;
        else if (c == 'q') B_Q_CASTLE = true;
    }
}

string serializeBoard() {
    string s;
    s.reserve(64);
    for (int r = 0; r < 8; r++)
        for (int c = 0; c < 8; c++)
            s += board[r][c];
    return s;
}

// ============================================================
//  Piece helpers
// ============================================================

bool isWhite(char c)  { return c >= 'A' && c <= 'Z'; }
bool isBlack(char c)  { return c >= 'a' && c <= 'z'; }
bool isEmpty(char c)  { return c == '.'; }

string colorOf(char c) {
    if (isWhite(c)) return "white";
    if (isBlack(c)) return "black";
    return "none";
}

bool inBounds(int r, int c) {
    return r >= 0 && r < 8 && c >= 0 && c < 8;
}

// ============================================================
//  Promotion helpers
// ============================================================

/**
 * Returns true when a pawn is moving to its promotion rank.
 * White pawns promote at row 0, black pawns at row 7.
 */
bool isPromotionMove(char piece, int toRow) {
    if (piece == 'P' && toRow == 0) return true;
    if (piece == 'p' && toRow == 7) return true;
    return false;
}

/**
 * Resolves the promoted piece character.
 * Accepts q/r/b/n (case-insensitive), defaults to queen.
 * Preserves the colour of the original pawn.
 */
char resolvePromotion(char pawn, char choice) {
    char lower = tolower(choice);
    if (lower != 'q' && lower != 'r' && lower != 'b' && lower != 'n')
        lower = 'q';                       // default to queen
    return isWhite(pawn) ? toupper(lower) : lower;
}

// ============================================================
//  Path obstruction check (rook / bishop / queen lines)
// ============================================================

bool pathClear(int fr, int fc, int tr, int tc) {
    int dr = (tr > fr) ? 1 : (tr < fr) ? -1 : 0;
    int dc = (tc > fc) ? 1 : (tc < fc) ? -1 : 0;
    int r = fr + dr, c = fc + dc;
    while (r != tr || c != tc) {
        if (!isEmpty(board[r][c])) return false;
        r += dr;
        c += dc;
    }
    return true;
}

// ============================================================
//  ATTACKED Logic (For Check/Checkmate detection)
// ============================================================

/**
 * Checks if a specific square (tr, tc) is being attacked by ANY piece
 * of the attackerColor.
 */
bool isSquareAttacked(int tr, int tc, string attackerColor) {
    char pKnight = (attackerColor == "white") ? 'N' : 'n';
    char pRook   = (attackerColor == "white") ? 'R' : 'r';
    char pBishop = (attackerColor == "white") ? 'B' : 'b';
    char pQueen  = (attackerColor == "white") ? 'Q' : 'q';
    char pPawn   = (attackerColor == "white") ? 'P' : 'p';
    char pKing   = (attackerColor == "white") ? 'K' : 'k';

    // Knight
    int nr[] = {-2, -2, -1, -1, 1, 1, 2, 2}, nc[] = {-1, 1, -2, 2, -2, 2, -1, 1};
    for (int i = 0; i < 8; i++) {
        int r = tr + nr[i], c = tc + nc[i];
        if (inBounds(r, c) && board[r][c] == pKnight) return true;
    }

    // Sliders
    int dr[] = {0, 0, 1, -1, 1, 1, -1, -1}, dc[] = {1, -1, 0, 0, 1, -1, 1, -1};
    for (int i = 0; i < 8; i++) {
        int r = tr + dr[i], c = tc + dc[i];
        while (inBounds(r, c)) {
            char p = board[r][c];
            if (p != '.') {
                if (colorOf(p) == attackerColor) {
                    char type = tolower(p);
                    if (i < 4 && (type == 'r' || type == 'q')) return true;
                    if (i >= 4 && (type == 'b' || type == 'q')) return true;
                }
                break;
            }
            r += dr[i]; c += dc[i];
        }
    }

    // Pawn
    int dir = (attackerColor == "white") ? 1 : -1;
    if (inBounds(tr + dir, tc - 1) && board[tr + dir][tc - 1] == pPawn) return true;
    if (inBounds(tr + dir, tc + 1) && board[tr + dir][tc + 1] == pPawn) return true;

    // King
    for (int r = tr - 1; r <= tr + 1; r++)
        for (int c = tc - 1; c <= tc + 1; c++)
            if (inBounds(r, c) && (r != tr || c != tc) && board[r][c] == pKing) return true;

    return false;
}

// ============================================================
//  Piece-specific movement rules
// ============================================================

bool validPawn(const string &color, int fr, int fc, int tr, int tc) {
    int dir      = (color == "white") ? -1 : 1;
    int startRow = (color == "white") ?  6 : 1;
    int dr = tr - fr;
    int dc = tc - fc;

    if (dc == 0 && dr == dir && isEmpty(board[tr][tc]))
        return true;

    if (dc == 0 && dr == 2 * dir && fr == startRow)
        if (isEmpty(board[fr + dir][fc]) && isEmpty(board[tr][tc]))
            return true;

    if (abs(dc) == 1 && dr == dir && !isEmpty(board[tr][tc]))
        return true;

    // En Passant
    if (abs(dc) == 1 && dr == dir && tr == EN_PASSANT_R && tc == EN_PASSANT_C)
        return true;

    return false;
}

bool validRook(int fr, int fc, int tr, int tc) {
    return (fr == tr || fc == tc) && pathClear(fr, fc, tr, tc);
}

bool validKnight(int fr, int fc, int tr, int tc) {
    int dr = abs(tr - fr), dc = abs(tc - fc);
    return (dr == 2 && dc == 1) || (dr == 1 && dc == 2);
}

bool validBishop(int fr, int fc, int tr, int tc) {
    return (abs(tr - fr) == abs(tc - fc)) && pathClear(fr, fc, tr, tc);
}

bool validQueen(int fr, int fc, int tr, int tc) {
    return validRook(fr, fc, tr, tc) || validBishop(fr, fc, tr, tc);
}

bool validKing(const string &color, int fr, int fc, int tr, int tc) {
    if (abs(tr - fr) <= 1 && abs(tc - fc) <= 1) return true;

    if (fr == tr && abs(tc - fc) == 2) {
        if (color == "white" && fr == 7 && fc == 4) {
            if (tc == 6 && W_K_CASTLE && isEmpty(board[7][5]) && isEmpty(board[7][6])) {
                if (!isSquareAttacked(7, 4, "black") && !isSquareAttacked(7, 5, "black") && !isSquareAttacked(7, 6, "black"))
                    return true;
            }
            if (tc == 2 && W_Q_CASTLE && isEmpty(board[7][3]) && isEmpty(board[7][2]) && isEmpty(board[7][1])) {
                if (!isSquareAttacked(7, 4, "black") && !isSquareAttacked(7, 3, "black") && !isSquareAttacked(7, 2, "black"))
                    return true;
            }
        } else if (color == "black" && fr == 0 && fc == 4) {
            if (tc == 6 && B_K_CASTLE && isEmpty(board[0][5]) && isEmpty(board[0][6])) {
                if (!isSquareAttacked(0, 4, "white") && !isSquareAttacked(0, 5, "white") && !isSquareAttacked(0, 6, "white"))
                    return true;
            }
            if (tc == 2 && B_Q_CASTLE && isEmpty(board[0][3]) && isEmpty(board[0][2]) && isEmpty(board[0][1])) {
                if (!isSquareAttacked(0, 4, "white") && !isSquareAttacked(0, 3, "white") && !isSquareAttacked(0, 2, "white"))
                    return true;
            }
        }
    }
    return false;
}

// ============================================================
//  Core validation
// ============================================================

bool validateMove(const string &turn, int fr, int fc, int tr, int tc, bool silent = false) {
    char piece = board[fr][fc];
    if (isEmpty(piece)) return false;
    if (colorOf(piece) != turn) return false;
    if (fr == tr && fc == tc) return false;

    char target = board[tr][tc];
    if (!isEmpty(target) && colorOf(target) == turn) return false;

    char type = static_cast<char>(tolower(static_cast<unsigned char>(piece)));
    bool ok = false;

    switch (type) {
        case 'p': ok = validPawn(turn, fr, fc, tr, tc); break;
        case 'r': ok = validRook(fr, fc, tr, tc);       break;
        case 'n': ok = validKnight(fr, fc, tr, tc);     break;
        case 'b': ok = validBishop(fr, fc, tr, tc);     break;
        case 'q': ok = validQueen(fr, fc, tr, tc);      break;
        case 'k': ok = validKing(turn, fr, fc, tr, tc); break;
    }

    if (ok && !silent) cout << "VALID" << endl;
    else if (!ok && !silent) cout << "INVALID Illegal move" << endl;

    return ok;
}

// ============================================================
//  Move struct & legality filter (forward declarations)
// ============================================================

struct Move {
    int fr, fc, tr, tc;
    char promoPiece;  // '\0' if not a promotion
};

pair<int,int> findKing(const string &color);
bool leavesKingInCheck(const Move &m, const string &side);

// ============================================================
//  Command Handlers
// ============================================================

void handleMoves(const string &turn, int row, int col) {
    char piece = board[row][col];
    if (isEmpty(piece) || colorOf(piece) != turn) {
        cout << "MOVES" << endl;
        return;
    }
    cout << "MOVES";
    for (int tr = 0; tr < 8; tr++) {
        for (int tc = 0; tc < 8; tc++) {
            if (validateMove(turn, row, col, tr, tc, true)) {
                // Filter out moves that leave own king in check
                Move m;
                m.fr = row; m.fc = col;
                m.tr = tr;  m.tc = tc;
                m.promoPiece = isPromotionMove(piece, tr)
                    ? (isWhite(piece) ? 'Q' : 'q') : '\0';
                if (leavesKingInCheck(m, turn)) continue;

                int cap   = isEmpty(board[tr][tc]) ? 0 : 1;
                int promo = isPromotionMove(piece, tr) ? 1 : 0;
                cout << " " << tr << " " << tc << " " << cap << " " << promo;
            }
        }
    }
    cout << endl;
}

// ============================================================
//  PROMOTE handler
// ============================================================

/**
 * Validates a promotion move, applies it on the board, and returns
 * the new 64-char board string so the Python layer stays in sync.
 *
 * Protocol:
 *   PROMOTE <board64> <turn> <fr> <fc> <tr> <tc> <promoPiece>
 *   -> PROMOTE <newBoard64>   (on success)
 *   -> INVALID <reason>       (on failure)
 */
void handlePromote(const string &turn, int fr, int fc, int tr, int tc,
                   char promoPiece) {
    char piece = board[fr][fc];

    // 1. The source must be a pawn of the current player
    if (isEmpty(piece) || colorOf(piece) != turn || tolower(piece) != 'p') {
        cout << "INVALID Not a pawn" << endl;
        return;
    }

    // 2. The move itself must be legal (single-push or diagonal capture)
    if (!validateMove(turn, fr, fc, tr, tc, true)) {
        cout << "INVALID Illegal move" << endl;
        return;
    }

    // 3. The target row must be the promotion rank
    if (!isPromotionMove(piece, tr)) {
        cout << "INVALID Not a promotion square" << endl;
        return;
    }

    // 4. Apply the move and promote
    board[tr][tc] = resolvePromotion(piece, promoPiece);
    board[fr][fc] = '.';

    cout << "PROMOTE " << serializeBoard() << endl;
}

// ============================================================
//  Minimax AI -- Evaluation + Alpha-Beta Search
// ============================================================

/**
 * Material values (centipawns).
 * Standard chess piece values used by most engines.
 */
int pieceValue(char p) {
    switch (tolower(p)) {
        case 'p': return 100;
        case 'n': return 320;
        case 'b': return 330;
        case 'r': return 500;
        case 'q': return 900;
        case 'k': return 20000;
        default:  return 0;
    }
}

/**
 * Piece-square tables for positional scoring.
 * Values are from White's perspective (row 0 = rank 8).
 * For black pieces the table is mirrored vertically.
 */

// clang-format off
static const int pawnTable[8][8] = {
    {  0,  0,  0,  0,  0,  0,  0,  0},
    { 50, 50, 50, 50, 50, 50, 50, 50},
    { 10, 10, 20, 30, 30, 20, 10, 10},
    {  5,  5, 10, 25, 25, 10,  5,  5},
    {  0,  0,  0, 20, 20,  0,  0,  0},
    {  5, -5,-10,  0,  0,-10, -5,  5},
    {  5, 10, 10,-20,-20, 10, 10,  5},
    {  0,  0,  0,  0,  0,  0,  0,  0}
};

static const int knightTable[8][8] = {
    {-50,-40,-30,-30,-30,-30,-40,-50},
    {-40,-20,  0,  0,  0,  0,-20,-40},
    {-30,  0, 10, 15, 15, 10,  0,-30},
    {-30,  5, 15, 20, 20, 15,  5,-30},
    {-30,  0, 15, 20, 20, 15,  0,-30},
    {-30,  5, 10, 15, 15, 10,  5,-30},
    {-40,-20,  0,  5,  5,  0,-20,-40},
    {-50,-40,-30,-30,-30,-30,-40,-50}
};

static const int bishopTable[8][8] = {
    {-20,-10,-10,-10,-10,-10,-10,-20},
    {-10,  0,  0,  0,  0,  0,  0,-10},
    {-10,  0, 10, 10, 10, 10,  0,-10},
    {-10,  5,  5, 10, 10,  5,  5,-10},
    {-10,  0,  5, 10, 10,  5,  0,-10},
    {-10, 10, 10, 10, 10, 10, 10,-10},
    {-10,  5,  0,  0,  0,  0,  5,-10},
    {-20,-10,-10,-10,-10,-10,-10,-20}
};

static const int rookTable[8][8] = {
    {  0,  0,  0,  0,  0,  0,  0,  0},
    {  5, 10, 10, 10, 10, 10, 10,  5},
    { -5,  0,  0,  0,  0,  0,  0, -5},
    { -5,  0,  0,  0,  0,  0,  0, -5},
    { -5,  0,  0,  0,  0,  0,  0, -5},
    { -5,  0,  0,  0,  0,  0,  0, -5},
    { -5,  0,  0,  0,  0,  0,  0, -5},
    {  0,  0,  0,  5,  5,  0,  0,  0}
};

static const int queenTable[8][8] = {
    {-20,-10,-10, -5, -5,-10,-10,-20},
    {-10,  0,  0,  0,  0,  0,  0,-10},
    {-10,  0,  5,  5,  5,  5,  0,-10},
    { -5,  0,  5,  5,  5,  5,  0, -5},
    {  0,  0,  5,  5,  5,  5,  0, -5},
    {-10,  5,  5,  5,  5,  5,  0,-10},
    {-10,  0,  5,  0,  0,  0,  0,-10},
    {-20,-10,-10, -5, -5,-10,-10,-20}
};

static const int kingMiddleTable[8][8] = {
    {-30,-40,-40,-50,-50,-40,-40,-30},
    {-30,-40,-40,-50,-50,-40,-40,-30},
    {-30,-40,-40,-50,-50,-40,-40,-30},
    {-30,-40,-40,-50,-50,-40,-40,-30},
    {-20,-30,-30,-40,-40,-30,-30,-20},
    {-10,-20,-20,-20,-20,-20,-20,-10},
    { 20, 20,  0,  0,  0,  0, 20, 20},
    { 20, 30, 10,  0,  0, 10, 30, 20}
};
// clang-format on

/**
 * Positional bonus for a single piece at (row, col).
 * White reads the table top-down; black mirrors it.
 */
int positionalBonus(char piece, int row, int col) {
    char type = static_cast<char>(tolower(static_cast<unsigned char>(piece)));
    int r = isWhite(piece) ? row : (7 - row);

    switch (type) {
        case 'p': return pawnTable[r][col];
        case 'n': return knightTable[r][col];
        case 'b': return bishopTable[r][col];
        case 'r': return rookTable[r][col];
        case 'q': return queenTable[r][col];
        case 'k': return kingMiddleTable[r][col];
        default:  return 0;
    }
}

/**
 * Static evaluation of the current board.
 * Positive => white advantage, negative => black advantage.
 */
int evaluate() {
    int score = 0;
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            char p = board[r][c];
            if (isEmpty(p)) continue;

            int val = pieceValue(p) + positionalBonus(p, r, c);
            score += isWhite(p) ? val : -val;
        }
    }
    // 3. Check Bonus: Prioritize moves that put the opponent under pressure
    pair<int, int> bKing = findKing("black");
    if (bKing.first != -1 && isSquareAttacked(bKing.first, bKing.second, "white"))
        score += 50;

    pair<int, int> wKing = findKing("white");
    if (wKing.first != -1 && isSquareAttacked(wKing.first, wKing.second, "black"))
        score -= 50;

    return score;
}

/**
 * Checks if the current board state is a draw due to insufficient material.
 * Simple cases: K vs K, K+N vs K, K+B vs K.
 */
bool isInsufficientMaterial() {
    int totalMinor = 0;
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            char p = board[r][c];
            if (p == '.') continue;
            char type = tolower(static_cast<unsigned char>(p));
            if (type == 'k') continue;
            // If there's a pawn, rook, or queen, checkmate is possible
            if (type == 'p' || type == 'r' || type == 'q') return false;
            totalMinor++;
        }
    }
    // Draw if total non-king pieces is 0 or 1
    return totalMinor <= 1;
}

/**
 * Generate all pseudo-legal moves for the given side.
 * Promotions automatically queen (keeping the search tree manageable).
 */
vector<Move> generateMoves(const string &side) {
    vector<Move> moves;
    moves.reserve(64);

    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            char p = board[r][c];
            if (isEmpty(p) || colorOf(p) != side) continue;

            for (int tr = 0; tr < 8; tr++) {
                for (int tc = 0; tc < 8; tc++) {
                    if (validateMove(side, r, c, tr, tc, true)) {
                        Move m;
                        m.fr = r; m.fc = c;
                        m.tr = tr; m.tc = tc;
                        m.promoPiece = isPromotionMove(p, tr) ? (isWhite(p) ? 'Q' : 'q') : '\0';
                        moves.push_back(m);
                    }
                }
            }
        }
    }
    return moves;
}

/**
 * Simple move-ordering heuristic: captures first, then promotions.
 * Helps alpha-beta prune more effectively.
 */
void orderMoves(vector<Move> &moves) {
    sort(moves.begin(), moves.end(), [](const Move &a, const Move &b) {
        int sa = 0, sb = 0;

        // Captures scored by victim value
        if (!isEmpty(board[a.tr][a.tc])) sa += pieceValue(board[a.tr][a.tc]) + 1000;
        if (!isEmpty(board[b.tr][b.tc])) sb += pieceValue(board[b.tr][b.tc]) + 1000;

        // Promotions
        if (a.promoPiece) sa += 900;
        if (b.promoPiece) sb += 900;

        return sa > sb;  // higher score first
    });
}

/**
 * Find the king position for a given colour.
 */
pair<int,int> findKing(const string &color) {
    char target = (color == "white") ? 'K' : 'k';
    for (int r = 0; r < 8; r++)
        for (int c = 0; c < 8; c++)
            if (board[r][c] == target) return {r, c};
    return {-1, -1};
}

/**
 * Check whether a move leaves the player's own king in check.
 * If it does, the move is illegal and should be skipped.
 */
bool leavesKingInCheck(const Move &m, const string &side) {
    char tempBoard[8][8];
    for(int i=0; i<8; i++) for(int j=0; j<8; j++) tempBoard[i][j] = board[i][j];

    // Apply move
    char p = board[m.fr][m.fc];
    
    // En Passant capture: diagonal pawn move to an empty square
    if (tolower(static_cast<unsigned char>(p)) == 'p' && m.fc != m.tc && board[m.tr][m.tc] == '.') {
        board[m.fr][m.tc] = '.'; 
    }

    board[m.tr][m.tc] = m.promoPiece ? m.promoPiece : p;
    board[m.fr][m.fc] = '.';

    // Castling rook move
    if (tolower(p) == 'k' && abs(m.tc - m.fc) == 2) {
        if (m.tc == 6) { board[m.fr][5] = board[m.fr][7]; board[m.fr][7] = '.'; }
        else { board[m.fr][3] = board[m.fr][0]; board[m.fr][0] = '.'; }
    }

    pair<int, int> kpos = findKing(side);
    bool inCheck = (kpos.first != -1) && isSquareAttacked(kpos.first, kpos.second, (side == "white" ? "black" : "white"));

    // Restore
    for(int i=0; i<8; i++) for(int j=0; j<8; j++) board[i][j] = tempBoard[i][j];
    return inCheck;
}

/**
 * Minimax with alpha-beta pruning.
 *
 *   depth      : remaining plies to search
 *   alpha/beta : pruning window
 *   maximizing : true when it is White's turn (White maximises)
 *
 * Returns the static evaluation at leaf nodes.
 */
int minimax(int depth, int alpha, int beta, bool maximizing) {
    if (depth == 0) return evaluate();

    string side = maximizing ? "white" : "black";
    vector<Move> moves = generateMoves(side);
    orderMoves(moves);

    // Filter out moves that leave own king in check
    vector<Move> legal;
    legal.reserve(moves.size());
    for (auto &m : moves) {
        if (!leavesKingInCheck(m, side))
            legal.push_back(m);
    }

    // No legal moves: checkmate or stalemate
    if (legal.empty()) {
        string opponent = maximizing ? "black" : "white";
        pair<int,int> kpos = findKing(side);
        if (kpos.first >= 0 && isSquareAttacked(kpos.first, kpos.second, opponent))
            return maximizing ? (-99999 + (100 - depth))   // checkmate (bad for side)
                              : ( 99999 - (100 - depth));
        return 0;  // stalemate
    }

    if (maximizing) {
        int maxEval = INT_MIN;
        for (auto &m : legal) {
            char src = board[m.fr][m.fc];
            char dst = board[m.tr][m.tc];
            board[m.tr][m.tc] = m.promoPiece ? m.promoPiece : src;
            board[m.fr][m.fc] = '.';

            int rook_fr = -1, rook_fc = -1, rook_tr = -1, rook_tc = -1;
            if (tolower(src) == 'k' && abs(m.tc - m.fc) == 2) {
                if (m.tc == 6) { rook_fr = m.fr; rook_fc = 7; rook_tr = m.tr; rook_tc = 5; }
                else if (m.tc == 2) { rook_fr = m.fr; rook_fc = 0; rook_tr = m.tr; rook_tc = 3; }
                if (rook_fr != -1) {
                    board[rook_tr][rook_tc] = board[rook_fr][rook_fc];
                    board[rook_fr][rook_fc] = '.';
                }
            }

            bool old_wk = W_K_CASTLE, old_wq = W_Q_CASTLE, old_bk = B_K_CASTLE, old_bq = B_Q_CASTLE;
            if (src == 'K') { W_K_CASTLE = false; W_Q_CASTLE = false; }
            if (src == 'k') { B_K_CASTLE = false; B_Q_CASTLE = false; }
            if (src == 'R') { if (m.fr == 7 && m.fc == 0) W_Q_CASTLE = false; else if (m.fr == 7 && m.fc == 7) W_K_CASTLE = false; }
            if (src == 'r') { if (m.fr == 0 && m.fc == 0) B_Q_CASTLE = false; else if (m.fr == 0 && m.fc == 7) B_K_CASTLE = false; }
            if (dst == 'R') { if (m.tr == 7 && m.tc == 0) W_Q_CASTLE = false; else if (m.tr == 7 && m.tc == 7) W_K_CASTLE = false; }
            if (dst == 'r') { if (m.tr == 0 && m.tc == 0) B_Q_CASTLE = false; else if (m.tr == 0 && m.tc == 7) B_K_CASTLE = false; }

            int eval = minimax(depth - 1, alpha, beta, false);

            W_K_CASTLE = old_wk; W_Q_CASTLE = old_wq; B_K_CASTLE = old_bk; B_Q_CASTLE = old_bq;

            board[m.fr][m.fc] = src;
            board[m.tr][m.tc] = dst;
            if (rook_fr != -1) {
                board[rook_fr][rook_fc] = board[rook_tr][rook_tc];
                board[rook_tr][rook_tc] = '.';
            }

            maxEval = max(maxEval, eval);
            alpha = max(alpha, eval);
            if (beta <= alpha) break;
        }
        return maxEval;
    } else {
        int minEval = INT_MAX;
        for (auto &m : legal) {
            char src = board[m.fr][m.fc];
            char dst = board[m.tr][m.tc];
            board[m.tr][m.tc] = m.promoPiece ? m.promoPiece : src;
            board[m.fr][m.fc] = '.';

            int rook_fr = -1, rook_fc = -1, rook_tr = -1, rook_tc = -1;
            if (tolower(src) == 'k' && abs(m.tc - m.fc) == 2) {
                if (m.tc == 6) { rook_fr = m.fr; rook_fc = 7; rook_tr = m.tr; rook_tc = 5; }
                else if (m.tc == 2) { rook_fr = m.fr; rook_fc = 0; rook_tr = m.tr; rook_tc = 3; }
                if (rook_fr != -1) {
                    board[rook_tr][rook_tc] = board[rook_fr][rook_fc];
                    board[rook_fr][rook_fc] = '.';
                }
            }

            bool old_wk = W_K_CASTLE, old_wq = W_Q_CASTLE, old_bk = B_K_CASTLE, old_bq = B_Q_CASTLE;
            if (src == 'K') { W_K_CASTLE = false; W_Q_CASTLE = false; }
            if (src == 'k') { B_K_CASTLE = false; B_Q_CASTLE = false; }
            if (src == 'R') { if (m.fr == 7 && m.fc == 0) W_Q_CASTLE = false; else if (m.fr == 7 && m.fc == 7) W_K_CASTLE = false; }
            if (src == 'r') { if (m.fr == 0 && m.fc == 0) B_Q_CASTLE = false; else if (m.fr == 0 && m.fc == 7) B_K_CASTLE = false; }
            if (dst == 'R') { if (m.tr == 7 && m.tc == 0) W_Q_CASTLE = false; else if (m.tr == 7 && m.tc == 7) W_K_CASTLE = false; }
            if (dst == 'r') { if (m.tr == 0 && m.tc == 0) B_Q_CASTLE = false; else if (m.tr == 0 && m.tc == 7) B_K_CASTLE = false; }

            int eval = minimax(depth - 1, alpha, beta, true);

            W_K_CASTLE = old_wk; W_Q_CASTLE = old_wq; B_K_CASTLE = old_bk; B_Q_CASTLE = old_bq;

            board[m.fr][m.fc] = src;
            board[m.tr][m.tc] = dst;
            if (rook_fr != -1) {
                board[rook_fr][rook_fc] = board[rook_tr][rook_tc];
                board[rook_tr][rook_tc] = '.';
            }

            minEval = min(minEval, eval);
            beta = min(beta, eval);
            if (beta <= alpha) break;
        }
        return minEval;
    }
}

// ============================================================
//  STATUS handler - check / checkmate / stalemate detection
// ============================================================

/**
 * STATUS <board64> <turn>
 * -> STATUS CHECK        (king is in check but has legal moves)
 * -> STATUS CHECKMATE    (king is in check and no legal moves)
 * -> STATUS STALEMATE    (king is NOT in check but no legal moves)
 * -> STATUS OK           (normal position)
 */
void handleStatus(const string &turn) {

    string opponent = (turn == "white") ? "black" : "white";
    pair<int,int> kpos = findKing(turn);
    bool inCheck = (kpos.first >= 0) &&
                   isSquareAttacked(kpos.first, kpos.second, opponent);

    // Count legal moves for the side to move
    vector<Move> moves = generateMoves(turn);
    bool hasLegal = false;
    for (auto &m : moves) {
        if (!leavesKingInCheck(m, turn)) {
            hasLegal = true;
            break;
        }
    }

    if (!hasLegal) {
        if (inCheck) cout << "STATUS CHECKMATE" << endl;
        else         cout << "STATUS STALEMATE" << endl;
    } else {
        if (inCheck) cout << "STATUS CHECK" << endl;
        else if (isInsufficientMaterial()) cout << "STATUS DRAW" << endl;
        else         cout << "STATUS OK" << endl;
    }
}

/**
 * NOTATION handler.
 *
 * Protocol:
 *   NOTATION <board64> <rights> <color> <fr> <fc> <tr> <tc>
 *   -> NOTATION <san>
 *
 * Generates accurate Standard Algebraic Notation (SAN) for a move,
 * including full disambiguation support (e.g., Rfe1, N5f3).
 */
void handleNotation(const string &turn, int fr, int fc, int tr, int tc) {
    char piece = board[fr][fc];
    if (isEmpty(piece)) {
        cout << "NOTATION ?" << endl;
        return;
    }

    char type = static_cast<char>(tolower(static_cast<unsigned char>(piece)));
    bool isCapture = !isEmpty(board[tr][tc]);
    string files = "abcdefgh";

    // 1. Castling
    if (type == 'k') {
        if (abs(tc - fc) == 2) {
            if (tc == 6) { cout << "NOTATION O-O" << endl; return; }
            if (tc == 2) { cout << "NOTATION O-O-O" << endl; return; }
        }
    }

    string res = "";
    if (type == 'p') {
        // Diagonal move for a pawn is always a capture (handles future En Passant support)
        if (fc != tc) {
            res += files[static_cast<string::size_type>(fc)];
            res += 'x';
        }
        res += files[static_cast<string::size_type>(tc)];
        res += to_string(8 - tr);

    } else {
        res += static_cast<char>(toupper(static_cast<unsigned char>(type)));

        // Disambiguation: Check if other pieces of the same type can move to the same square
        vector<pair<int, int>> others;
        for (int r = 0; r < 8; r++) {
            for (int c = 0; c < 8; c++) {
                if (r == fr && c == fc) continue;
                if (board[r][c] == piece) {
                    if (validateMove(turn, r, c, tr, tc, true)) {
                        Move m = {r, c, tr, tc, '\0'};
                        if (!leavesKingInCheck(m, turn)) {
                            others.push_back({r, c});
                        }
                    }
                }
            }
        }

        if (!others.empty()) {
            bool sameFile = false;
            bool sameRank = false;
            for (auto &p : others) {
                if (p.second == fc) sameFile = true;
                if (p.first == fr) sameRank = true;
            }

            if (!sameFile) {
                res += files[static_cast<string::size_type>(fc)];
            } else if (!sameRank) {
                res += to_string(8 - fr);
            } else {
                res += files[static_cast<string::size_type>(fc)];
                res += to_string(8 - fr);
            }
        }

        if (isCapture) res += 'x';
        res += files[static_cast<string::size_type>(tc)];
        res += to_string(8 - tr);
    }

    // Apply move temporarily to check for Check/Checkmate
    char src = board[fr][fc];
    char dst = board[tr][tc];
    // Use the piece type from board for status check (ignore promotion choice for now)
    board[tr][tc] = src;
    board[fr][fc] = '.';

    string opponent = (turn == "white") ? "black" : "white";
    pair<int, int> kpos = findKing(opponent);
    if (kpos.first != -1 && isSquareAttacked(kpos.first, kpos.second, turn)) {
        vector<Move> oppMoves = generateMoves(opponent);
        bool hasLegal = false;
        for (auto &m : oppMoves) {
            if (!leavesKingInCheck(m, opponent)) {
                hasLegal = true;
                break;
            }
        }
        res += hasLegal ? "+" : "#";
    }

    // Undo move
    board[fr][fc] = src;
    board[tr][tc] = dst;

    cout << "NOTATION " << res << endl;
}

/**
 * BESTMOVE handler.
 *
 * Protocol:
 *   BESTMOVE <board64> <turn> <depth>
 *   -> BESTMOVE <fr> <fc> <tr> <tc>
 *   -> BESTMOVE NONE            (no legal moves)
 *
 * Runs minimax to the requested depth and returns the best move
 * for the given side.
 */
void handleBestMove(const string &turn, int depth) {
    bool maximizing = (turn == "white");
    vector<Move> moves = generateMoves(turn);
    orderMoves(moves);

    vector<Move> legal;
    legal.reserve(moves.size());
    for (auto &m : moves) {
        if (!leavesKingInCheck(m, turn))
            legal.push_back(m);
    }

    if (legal.empty()) {
        cout << "BESTMOVE NONE" << endl;
        return;
    }

    Move best = legal[0];
    int bestVal = maximizing ? INT_MIN : INT_MAX;

    for (auto &m : legal) {
        char src = board[m.fr][m.fc];
        char dst = board[m.tr][m.tc];
        board[m.tr][m.tc] = m.promoPiece ? m.promoPiece : src;
        board[m.fr][m.fc] = '.';

        int rook_fr = -1, rook_fc = -1, rook_tr = -1, rook_tc = -1;
        if (tolower(src) == 'k' && abs(m.tc - m.fc) == 2) {
            if (m.tc == 6) { rook_fr = m.fr; rook_fc = 7; rook_tr = m.tr; rook_tc = 5; }
            else if (m.tc == 2) { rook_fr = m.fr; rook_fc = 0; rook_tr = m.tr; rook_tc = 3; }
            if (rook_fr != -1) {
                board[rook_tr][rook_tc] = board[rook_fr][rook_fc];
                board[rook_fr][rook_fc] = '.';
            }
        }

        bool old_wk = W_K_CASTLE, old_wq = W_Q_CASTLE, old_bk = B_K_CASTLE, old_bq = B_Q_CASTLE;
        if (src == 'K') { W_K_CASTLE = false; W_Q_CASTLE = false; }
        if (src == 'k') { B_K_CASTLE = false; B_Q_CASTLE = false; }
        if (src == 'R') { if (m.fr == 7 && m.fc == 0) W_Q_CASTLE = false; else if (m.fr == 7 && m.fc == 7) W_K_CASTLE = false; }
        if (src == 'r') { if (m.fr == 0 && m.fc == 0) B_Q_CASTLE = false; else if (m.fr == 0 && m.fc == 7) B_K_CASTLE = false; }
        if (dst == 'R') { if (m.tr == 7 && m.tc == 0) W_Q_CASTLE = false; else if (m.tr == 7 && m.tc == 7) W_K_CASTLE = false; }
        if (dst == 'r') { if (m.tr == 0 && m.tc == 0) B_Q_CASTLE = false; else if (m.tr == 0 && m.tc == 7) B_K_CASTLE = false; }

        int eval = minimax(depth - 1, INT_MIN, INT_MAX, !maximizing);

        W_K_CASTLE = old_wk; W_Q_CASTLE = old_wq; B_K_CASTLE = old_bk; B_Q_CASTLE = old_bq;

        board[m.fr][m.fc] = src;
        board[m.tr][m.tc] = dst;
        if (rook_fr != -1) {
            board[rook_fr][rook_fc] = board[rook_tr][rook_tc];
            board[rook_tr][rook_tc] = '.';
        }

        if (maximizing) {
            if (eval > bestVal) { bestVal = eval; best = m; }
        } else {
            if (eval < bestVal) { bestVal = eval; best = m; }
        }
    }

    cout << "BESTMOVE " << best.fr << " " << best.fc
         << " " << best.tr << " " << best.tc << endl;
}

int main() {
    string command;
    while (cin >> command) {
        if (command == "VALIDATE") {
            string b, rights, t; int epR, epC, fr, fc, tr, tc;
            cin >> b >> rights >> t >> epR >> epC >> fr >> fc >> tr >> tc;
            loadBoard(b);
            loadCastlingRights(rights);
            EN_PASSANT_R = epR; EN_PASSANT_C = epC;
            validateMove(t, fr, fc, tr, tc);
        } 
        else if (command == "MOVES") {
            string b, rights, t; int epR, epC, r, c;
            cin >> b >> rights >> t >> epR >> epC >> r >> c;
            loadBoard(b);
            loadCastlingRights(rights);
            EN_PASSANT_R = epR; EN_PASSANT_C = epC;
            handleMoves(t, r, c);
        } 
        else if (command == "ATTACKED") {
            string b, rights, attackerColor; int r, c;
            cin >> b >> rights >> attackerColor >> r >> c;
            loadBoard(b);
            loadCastlingRights(rights);
            if (isSquareAttacked(r, c, attackerColor)) cout << "YES" << endl;
            else cout << "NO" << endl;
        }
        else if (command == "PROMOTE") {
            string b, rights, t; int epR, epC, fr, fc, tr, tc; char promo;
            cin >> b >> rights >> t >> epR >> epC >> fr >> fc >> tr >> tc >> promo;
            loadBoard(b);
            loadCastlingRights(rights);
            EN_PASSANT_R = epR; EN_PASSANT_C = epC;
            handlePromote(t, fr, fc, tr, tc, promo);
        }
        else if (command == "STATUS") {
            string b, rights, t; int epR, epC;
            cin >> b >> rights >> t >> epR >> epC;
            loadBoard(b);
            loadCastlingRights(rights);
            EN_PASSANT_R = epR; EN_PASSANT_C = epC;
            handleStatus(t);
        }
        else if (command == "BESTMOVE") {
            string b, rights, t; int epR, epC, depth;
            cin >> b >> rights >> t >> epR >> epC >> depth;
            loadBoard(b);
            loadCastlingRights(rights);
            EN_PASSANT_R = epR; EN_PASSANT_C = epC;
            handleBestMove(t, depth);
        }
        else if (command == "NOTATION") {
            string b, rights, t; int epR, epC, fr, fc, tr, tc;
            cin >> b >> rights >> t >> epR >> epC >> fr >> fc >> tr >> tc;
            loadBoard(b);
            loadCastlingRights(rights);
            EN_PASSANT_R = epR; EN_PASSANT_C = epC;
            handleNotation(t, fr, fc, tr, tc);
        }
    }
    return 0;
}
