/**
 * Checkora Chess Engine
 *
 * Validates chess moves and computes legal move sets.
 * Communicates with the Django backend via stdin/stdout.
 *
 * Protocol:
 *   VALIDATE <board64> <turn> <fr> <fc> <tr> <tc>
 *     -> VALID | INVALID <reason>
 *
 *   MOVES <board64> <turn> <row> <col>
 *     -> MOVES [<row> <col> <is_capture> ...]
 */

#include <iostream>
#include <string>
#include <cmath>
#include <cctype>

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
//  Piece-specific movement rules
// ============================================================

bool validPawn(const string &color, int fr, int fc, int tr, int tc) {
    int dir      = (color == "white") ? -1 : 1;
    int startRow = (color == "white") ?  6 : 1;
    int dr = tr - fr;
    int dc = tc - fc;

    // Forward one square
    if (dc == 0 && dr == dir && isEmpty(board[tr][tc]))
        return true;

    // Forward two squares from starting rank
    if (dc == 0 && dr == 2 * dir && fr == startRow)
        if (isEmpty(board[fr + dir][fc]) && isEmpty(board[tr][tc]))
            return true;

    // Diagonal capture
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

/**
 * Validate a move.  Prints the result to stdout and returns the
 * boolean validity so callers (MOVES command) can re-use the logic
 * without extra I/O.
 */
bool validateMove(const string &turn, int fr, int fc, int tr, int tc,
                  bool silent = false) {
    char piece = board[fr][fc];

    if (isEmpty(piece)) {
        if (!silent) cout << "INVALID No piece on source square" << endl;
        return false;
    }
    if (colorOf(piece) != turn) {
        if (!silent) cout << "INVALID Not your turn" << endl;
        return false;
    }
    if (fr == tr && fc == tc) {
        if (!silent) cout << "INVALID Must move to a different square" << endl;
        return false;
    }

    char target = board[tr][tc];
    if (!isEmpty(target) && colorOf(target) == turn) {
        if (!silent) cout << "INVALID Cannot capture your own piece" << endl;
        return false;
    }

    char type = tolower(piece);
    bool ok = false;

    switch (type) {
        case 'p': ok = validPawn(turn, fr, fc, tr, tc); break;
        case 'r': ok = validRook(fr, fc, tr, tc);       break;
        case 'n': ok = validKnight(fr, fc, tr, tc);     break;
        case 'b': ok = validBishop(fr, fc, tr, tc);     break;
        case 'q': ok = validQueen(fr, fc, tr, tc);      break;
        case 'k': ok = validKing(fr, fc, tr, tc);       break;
        default:
            if (!silent) cout << "INVALID Unknown piece type" << endl;
            return false;
    }

    if (!ok && !silent)
        cout << "INVALID Illegal move for this piece" << endl;
    if (ok && !silent)
        cout << "VALID" << endl;

    return ok;
}

// ============================================================
//  MOVES command — enumerate every legal destination
// ============================================================

void printValidMoves(const string &turn, int row, int col) {
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

// ============================================================
//  Entry point
// ============================================================

int main() {
    string command;
    if (!(cin >> command)) return 0;

    if (command == "VALIDATE") {
        string boardStr, turn;
        int fr, fc, tr, tc;
        cin >> boardStr >> turn >> fr >> fc >> tr >> tc;

        if (boardStr.length() != 64) {
            cout << "INVALID Bad board data" << endl;
            return 0;
        }
        loadBoard(boardStr);
        validateMove(turn, fr, fc, tr, tc);

    } else if (command == "MOVES") {
        string boardStr, turn;
        int row, col;
        cin >> boardStr >> turn >> row >> col;

        if (boardStr.length() != 64) {
            cout << "MOVES" << endl;
            return 0;
        }
        loadBoard(boardStr);
        printValidMoves(turn, row, col);

    } else {
        // Legacy fallback — echo input as VALID
        cout << "VALID " << command << endl;
    }

    return 0;
}
