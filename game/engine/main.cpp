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

void loadBoard(const string &s) {
    for (int i = 0; i < 64; i++)
        board[i / 8][i % 8] = s[static_cast<std::string::size_type>(i)];
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
    // 1. Knight Attacks
    int nr[] = {-2, -2, -1, -1, 1, 1, 2, 2};
    int nc[] = {-1, 1, -2, 2, -2, 2, -1, 1};
    char targetKnight = (attackerColor == "white") ? 'N' : 'n';
    for (int i = 0; i < 8; i++) {
        int r = tr + nr[i], c = tc + nc[i];
        if (inBounds(r, c) && board[r][c] == targetKnight) return true;
    }

    // 2. Sliding Attacks (Rook, Bishop, Queen)
    int dr[] = {0, 0, 1, -1, 1, 1, -1, -1};
    int dc[] = {1, -1, 0, 0, 1, -1, 1, -1};
    for (int i = 0; i < 8; i++) {
        int r = tr + dr[i], c = tc + dc[i];
        while (inBounds(r, c)) {
            char p = board[r][c];
            if (!isEmpty(p)) {
                if (colorOf(p) == attackerColor) {
                    char type = static_cast<char>(tolower(static_cast<unsigned char>(p)));
                    if (i < 4 && (type == 'r' || type == 'q')) return true;
                    if (i >= 4 && (type == 'b' || type == 'q')) return true;
                }
                break; // Path blocked
            }
            r += dr[i]; c += dc[i];
        }
    }

    // 3. Pawn Attacks
    int pDir = (attackerColor == "white") ? 1 : -1; // Attacking FROM this direction
    char targetPawn = (attackerColor == "white") ? 'P' : 'p';
    if (inBounds(tr + pDir, tc - 1) && board[tr + pDir][tc - 1] == targetPawn) return true;
    if (inBounds(tr + pDir, tc + 1) && board[tr + pDir][tc + 1] == targetPawn) return true;

    // 4. King Attacks (Preventing King moving into King)
    char targetKing = (attackerColor == "white") ? 'K' : 'k';
    for (int r = tr - 1; r <= tr + 1; r++) {
        for (int c = tc - 1; c <= tc + 1; c++) {
            if (inBounds(r, c) && (r != tr || c != tc)) {
                if (board[r][c] == targetKing) return true;
            }
        }
    }

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

bool validKing(int fr, int fc, int tr, int tc) {
    return abs(tr - fr) <= 1 && abs(tc - fc) <= 1;
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
        case 'k': ok = validKing(fr, fc, tr, tc);       break;
    }

    if (ok && !silent) cout << "VALID" << endl;
    else if (!ok && !silent) cout << "INVALID Illegal move" << endl;

    return ok;
}

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
    return score;
}

/**
 * Represents a single move with from/to squares.
 */
struct Move {
    int fr, fc, tr, tc;
    char promoPiece;  // '\0' if not a promotion
};

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
    // Save state
    char srcPiece = board[m.fr][m.fc];
    char dstPiece = board[m.tr][m.tc];

    // Apply
    board[m.tr][m.tc] = m.promoPiece ? m.promoPiece : srcPiece;
    board[m.fr][m.fc] = '.';

    string opponent = (side == "white") ? "black" : "white";
    pair<int,int> kpos = findKing(side);
    bool inCheck = (kpos.first >= 0) && isSquareAttacked(kpos.first, kpos.second, opponent);

    // Undo
    board[m.fr][m.fc] = srcPiece;
    board[m.tr][m.tc] = dstPiece;

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

            int eval = minimax(depth - 1, alpha, beta, false);

            board[m.fr][m.fc] = src;
            board[m.tr][m.tc] = dst;

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

            int eval = minimax(depth - 1, alpha, beta, true);

            board[m.fr][m.fc] = src;
            board[m.tr][m.tc] = dst;

            minEval = min(minEval, eval);
            beta = min(beta, eval);
            if (beta <= alpha) break;
        }
        return minEval;
    }
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

        int eval = minimax(depth - 1, INT_MIN, INT_MAX, !maximizing);

        board[m.fr][m.fc] = src;
        board[m.tr][m.tc] = dst;

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
            string b, t; int fr, fc, tr, tc;
            cin >> b >> t >> fr >> fc >> tr >> tc;
            loadBoard(b);
            validateMove(t, fr, fc, tr, tc);
        } 
        else if (command == "MOVES") {
            string b, t; int r, c;
            cin >> b >> t >> r >> c;
            loadBoard(b);
            handleMoves(t, r, c);
        } 
        else if (command == "ATTACKED") {
            string b, attackerColor; int r, c;
            cin >> b >> attackerColor >> r >> c;
            loadBoard(b);
            if (isSquareAttacked(r, c, attackerColor)) cout << "YES" << endl;
            else cout << "NO" << endl;
        }
        else if (command == "PROMOTE") {
            string b, t; int fr, fc, tr, tc; char promo;
            cin >> b >> t >> fr >> fc >> tr >> tc >> promo;
            loadBoard(b);
            handlePromote(t, fr, fc, tr, tc, promo);
        }
        else if (command == "BESTMOVE") {
            string b, t; int depth;
            cin >> b >> t >> depth;
            loadBoard(b);
            handleBestMove(t, depth);
        }
    }
    return 0;
}