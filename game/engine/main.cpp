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
 * -> MOVES [<row> <col> <is_capture> ...]
 * * ATTACKED <board64> <attackerColor> <row> <col>
 * -> YES | NO
 */

#include <iostream>
#include <string>
#include <cmath>
#include <cctype>
#include <vector>

using namespace std;

// ============================================================
//  Board representation
// ============================================================

char board[8][8];

void loadBoard(const string &s) {
    for (int i = 0; i < 64; i++)
        board[i / 8][i % 8] = s[i];
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
                    char type = tolower(p);
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

    char type = tolower(piece);
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
                int cap = isEmpty(board[tr][tc]) ? 0 : 1;
                cout << " " << tr << " " << tc << " " << cap;
            }
        }
    }
    cout << endl;
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
    }
    return 0;
}