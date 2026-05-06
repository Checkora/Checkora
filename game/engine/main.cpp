#include <iostream>
#include <string>
#include <vector>
#include <cmath>
#include <algorithm>
#include <climits>

using namespace std;

// ================= BOARD =================
char board[8][8];

// ================= HELPERS =================
bool inBounds(int r, int c) {
    return r >= 0 && r < 8 && c >= 0 && c < 8;
}

bool isWhite(char c) { return c >= 'A' && c <= 'Z'; }
bool isBlack(char c) { return c >= 'a' && c <= 'z'; }
bool isEmpty(char c) { return c == '.'; }

string colorOf(char c) {
    if (isWhite(c)) return "white";
    if (isBlack(c)) return "black";
    return "none";
}

void loadBoard(const string &s) {
    for (int i = 0; i < 64; i++)
        board[i / 8][i % 8] = s[i];
}

// ================= MOVE STRUCT (NO tuple issues) =================
struct Move {
    int fr, fc, tr, tc;
};

vector<Move> moveList;

// ================= PATH CHECK =================
bool pathClear(int fr, int fc, int tr, int tc) {
    int dr = (tr > fr) ? 1 : (tr < fr ? -1 : 0);
    int dc = (tc > fc) ? 1 : (tc < fc ? -1 : 0);

    int r = fr + dr, c = fc + dc;
    while (r != tr || c != tc) {
        if (!isEmpty(board[r][c])) return false;
        r += dr; c += dc;
    }
    return true;
}

// ================= PIECES =================
bool pawnMove(string turn, int fr, int fc, int tr, int tc) {
    int dir = (turn == "white") ? -1 : 1;

    if (fc == tc && isEmpty(board[tr][tc]) && tr - fr == dir)
        return true;

    if (abs(fc - tc) == 1 && tr - fr == dir && !isEmpty(board[tr][tc]))
        return colorOf(board[tr][tc]) != turn;

    return false;
}

bool rookMove(int fr, int fc, int tr, int tc) {
    return (fr == tr || fc == tc) && pathClear(fr, fc, tr, tc);
}

bool bishopMove(int fr, int fc, int tr, int tc) {
    return abs(fr - tr) == abs(fc - tc) && pathClear(fr, fc, tr, tc);
}

bool queenMove(int fr, int fc, int tr, int tc) {
    return rookMove(fr, fc, tr, tc) || bishopMove(fr, fc, tr, tc);
}

bool knightMove(int fr, int fc, int tr, int tc) {
    int dr = abs(fr - tr), dc = abs(fc - tc);
    return (dr == 2 && dc == 1) || (dr == 1 && dc == 2);
}

bool kingMove(int fr, int fc, int tr, int tc) {
    return abs(fr - tr) <= 1 && abs(fc - tc) <= 1;
}

// ================= ATTACK CHECK =================
bool isSquareAttacked(int tr, int tc, string attacker) {
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            char p = board[r][c];
            if (isEmpty(p) || colorOf(p) != attacker) continue;

            char t = tolower(p);

            if (t == 'p') {
                int dir = (attacker == "white") ? -1 : 1;
                if (r + dir == tr && (c + 1 == tc || c - 1 == tc))
                    return true;
            }
            if (t == 'n' && knightMove(r, c, tr, tc)) return true;
            if (t == 'r' && rookMove(r, c, tr, tc)) return true;
            if (t == 'b' && bishopMove(r, c, tr, tc)) return true;
            if (t == 'q' && queenMove(r, c, tr, tc)) return true;
            if (t == 'k' && kingMove(r, c, tr, tc)) return true;
        }
    }
    return false;
}

// ================= KING FIND =================
pair<int,int> findKing(string color) {
    char k = (color == "white") ? 'K' : 'k';

    for (int r = 0; r < 8; r++)
        for (int c = 0; c < 8; c++)
            if (board[r][c] == k)
                return make_pair(r, c);

    return make_pair(-1, -1);
}

// ================= VALID MOVE =================
bool validMove(string turn, int fr, int fc, int tr, int tc) {
    char p = board[fr][fc];
    if (isEmpty(p) || colorOf(p) != turn) return false;

    char t = tolower(p);
    bool ok = false;

    if (t == 'p') ok = pawnMove(turn, fr, fc, tr, tc);
    else if (t == 'r') ok = rookMove(fr, fc, tr, tc);
    else if (t == 'n') ok = knightMove(fr, fc, tr, tc);
    else if (t == 'b') ok = bishopMove(fr, fc, tr, tc);
    else if (t == 'q') ok = queenMove(fr, fc, tr, tc);
    else if (t == 'k') ok = kingMove(fr, fc, tr, tc);

    if (!ok) return false;

    // simulate move
    char temp = board[tr][tc];
    board[tr][tc] = p;
    board[fr][fc] = '.';

    pair<int,int> kp = findKing(turn);
    bool safe = !isSquareAttacked(kp.first, kp.second,
                 (turn == "white") ? "black" : "white");

    board[fr][fc] = p;
    board[tr][tc] = temp;

    return safe;
}

// ================= GENERATE MOVES =================
void generateMoves(string turn, vector<Move> &moves) {
    moves.clear();

    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            if (isEmpty(board[r][c]) || colorOf(board[r][c]) != turn)
                continue;

            for (int i = 0; i < 8; i++) {
                for (int j = 0; j < 8; j++) {
                    if (validMove(turn, r, c, i, j)) {
                        Move m;
                        m.fr = r; m.fc = c;
                        m.tr = i; m.tc = j;
                        moves.push_back(m);
                    }
                }
            }
        }
    }
}

// ================= EVALUATION =================
int eval() {
    int score = 0;

    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            char p = board[r][c];
            if (isEmpty(p)) continue;

            int val = 0;
            switch (tolower(p)) {
                case 'p': val = 100; break;
                case 'n': val = 320; break;
                case 'b': val = 330; break;
                case 'r': val = 500; break;
                case 'q': val = 900; break;
                case 'k': val = 20000; break;
            }

            score += isWhite(p) ? val : -val;
        }
    }
    return score;
}

// ================= MINIMAX + ALPHA BETA =================
int minimax(int depth, bool maximizing, int alpha, int beta) {
    if (depth == 0) return eval();

    vector<Move> moves;
    generateMoves(maximizing ? "white" : "black", moves);

    if (moves.empty()) return eval();

    if (maximizing) {
        int best = INT_MIN;

        for (int i = 0; i < (int)moves.size(); i++) {
            Move m = moves[i];

            char p = board[m.fr][m.fc];
            char t = board[m.tr][m.tc];

            board[m.tr][m.tc] = p;
            board[m.fr][m.fc] = '.';

            best = max(best, minimax(depth - 1, false, alpha, beta));

            board[m.fr][m.fc] = p;
            board[m.tr][m.tc] = t;

            alpha = max(alpha, best);
            if (beta <= alpha) break;
        }

        return best;
    } else {
        int best = INT_MAX;

        for (int i = 0; i < (int)moves.size(); i++) {
            Move m = moves[i];

            char p = board[m.fr][m.fc];
            char t = board[m.tr][m.tc];

            board[m.tr][m.tc] = p;
            board[m.fr][m.fc] = '.';

            best = min(best, minimax(depth - 1, true, alpha, beta));

            board[m.fr][m.fc] = p;
            board[m.tr][m.tc] = t;

            beta = min(beta, best);
            if (beta <= alpha) break;
        }

        return best;
    }
}

// ================= BEST MOVE =================
void bestMove(string turn, int depth) {
    vector<Move> moves;
    generateMoves(turn, moves);

    int bestScore = (turn == "white") ? INT_MIN : INT_MAX;
    Move best = {-1,-1,-1,-1};

    for (int i = 0; i < (int)moves.size(); i++) {
        Move m = moves[i];

        char p = board[m.fr][m.fc];
        char t = board[m.tr][m.tc];

        board[m.tr][m.tc] = p;
        board[m.fr][m.fc] = '.';

        int score = minimax(depth - 1,
                            turn != "white",
                            INT_MIN,
                            INT_MAX);

        board[m.fr][m.fc] = p;
        board[m.tr][m.tc] = t;

        if (turn == "white") {
            if (score > bestScore) {
                bestScore = score;
                best = m;
            }
        } else {
            if (score < bestScore) {
                bestScore = score;
                best = m;
            }
        }
    }

    cout << "BESTMOVE "
         << best.fr << " "
         << best.fc << " "
         << best.tr << " "
         << best.tc << "\n";
}

// ================= STATUS =================
void status(string turn) {
    pair<int,int> k = findKing(turn);
    bool check = isSquareAttacked(k.first, k.second,
                 (turn == "white") ? "black" : "white");

    vector<Move> moves;
    generateMoves(turn, moves);

    if (moves.empty() && check) cout << "CHECKMATE\n";
    else if (moves.empty()) cout << "STALEMATE\n";
    else if (check) cout << "CHECK\n";
    else cout << "OK\n";
}

// ================= MAIN =================
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string cmd;

    while (cin >> cmd) {

        if (cmd == "VALIDATE") {
            string b, t;
            int fr, fc, tr, tc;
            cin >> b >> t >> fr >> fc >> tr >> tc;
            loadBoard(b);
            cout << (validMove(t, fr, fc, tr, tc) ? "VALID\n" : "INVALID\n");
        }

        else if (cmd == "STATUS") {
            string b, t;
            cin >> b >> t;
            loadBoard(b);
            status(t);
        }

        else if (cmd == "BESTMOVE") {
            string b, t;
            int d;
            cin >> b >> t >> d;
            loadBoard(b);
            bestMove(t, d);
        }
    }

    return 0;
}