/**
 * Checkora Chess Engine
 *
 * Lists legal moves, judges positions and searches for the best move for
 * the Django backend, which talks to it over stdin/stdout.
 * game/engine/main.py implements the same protocol, rules, evaluation
 * and search and must be kept in step with this file: given the same
 * command without a time limit, both give the same reply apart from TIME
 * and ENGINE. That covers the order in which moves are generated and
 * tried and the transposition table (two entries per slot, 2^19 slots,
 * the first keeping the deepest search).
 *
 * Protocol: one command per line, exactly one reply line per command.
 * <board64> is 64 characters, rank 8 first, "." for an empty square.
 * <rights> is a subset of "KQkq" or "-", <turn> is "white" or "black",
 * <epRow> <epCol> is the en passant target square or "-1 -1".
 *
 * VERSION
 * -> VERSION <protocolVersion>
 *
 * MOVES <board64> <rights> <turn> <epRow> <epCol> <row> <col>
 * -> MOVES [<row> <col> <is_capture> <is_promotion> ...]
 *
 * ATTACKED <board64> <rights> <attackerColor> <row> <col>
 * -> YES | NO
 *
 * PROMOTE <board64> <rights> <turn> <epRow> <epCol> <fr> <fc> <tr> <tc> [promoPiece]
 * -> PROMOTE <newBoard64>   | INVALID <reason>
 *
 * STATUS <board64> <rights> <turn> <epRow> <epCol>
 * -> STATUS CHECK | CHECKMATE | STALEMATE | DRAW | OK
 *
 * NOTATION <board64> <rights> <turn> <epRow> <epCol> <fr> <fc> <tr> <tc> [promoPiece]
 * -> NOTATION <san>
 * -> NOTATION ?               (the move is not legal)
 *
 * EVAL <board64> <rights> <turn> <epRow> <epCol>
 * -> EVAL <centipawns, positive is good for White>
 *
 * PERFT <board64> <rights> <turn> <epRow> <epCol> <depth>
 * -> PERFT <leaf nodes>
 *
 * BESTMOVE <board64> <rights> <turn> <epRow> <epCol> <depth> [timeLimitMs
 *          [halfmoveClock [alternatives [<placement> <w|b> <rights> <ep>]...]]]
 * -> BESTMOVE <fr> <fc> <tr> <tc> EVAL <cp> [ALTS (<fr> <fc> <tr> <tc> <cp>)...]
 *    DEPTH <d> NODES <n> TTHITS <n> TIME <ms> ENGINE cpp STATUS completed|timeout
 * -> BESTMOVE NONE            (no legal moves)
 *    A time limit of 0 or less means none. alternatives (default 0) is
 *    how many of the next best moves to score as well; they are searched
 *    to the same depth as the best move, so their scores compare with
 *    EVAL, and one that the time limit cuts off is left out.
 *    The trailing groups of four tokens are the earlier positions of the
 *    game since the last capture or pawn move (FEN piece placement, side,
 *    castling rights, en passant square as "row,col" or "-"). A position
 *    the search reaches again counts as a draw when its earlier occurrence
 *    is on the line being searched, or when it has occurred twice before
 *    in the game. A promotion is always to a queen.
 *
 * EVAL and PERFT are not used by the web app; the tests use them to check
 * that both engines evaluate alike and generate the right moves.
 *
 * A line that cannot be parsed is answered with "ERROR <reason>".
 */

#include <algorithm>
#include <cctype>
#include <cerrno>
#include <chrono>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace std;

static const int PROTOCOL_VERSION = 2;

// ============================================================
//  Board representation
// ============================================================
//
// 10x12 mailbox: the 64 squares sit inside a border of OFFBOARD cells so a
// piece stepping off the board lands on a sentinel instead of needing a
// bounds check. Row 0 is rank 8, as in the protocol.

enum { EMPTY, WP, WN, WB, WR, WQ, WK, BP, BN, BB, BR, BQ, BK, OFFBOARD };
enum { PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING };
enum { WHITE, BLACK };
enum { CASTLE_WK = 1, CASTLE_WQ = 2, CASTLE_BK = 4, CASTLE_BQ = 8 };

static const char PIECE_CHARS[] = ".PNBRQKpnbrqk";

static inline int SQ(int row, int col) { return 21 + row * 10 + col; }
static inline int rowOf(int sq) { return sq / 10 - 2; }
static inline int colOf(int sq) { return sq % 10 - 1; }
static inline int colorOf(int piece) { return piece >= BP ? BLACK : WHITE; }
static inline int typeOf(int piece) { return (piece - 1) % 6; }
static inline int makePiece(int color, int type) { return color * 6 + type + 1; }

static const int A1 = 91, B1 = 92, C1 = 93, D1 = 94, E1 = 95, F1 = 96, G1 = 97, H1 = 98;
static const int A8 = 21, B8 = 22, C8 = 23, D8 = 24, E8 = 25, F8 = 26, G8 = 27, H8 = 28;

static const int KNIGHT_DIRS[8] = {-21, -19, -12, -8, 8, 12, 19, 21};
static const int KING_DIRS[8] = {-11, -10, -9, -1, 1, 9, 10, 11};
static const int BISHOP_DIRS[4] = {-11, -9, 9, 11};
static const int ROOK_DIRS[4] = {-10, -1, 1, 10};

/** The directions a bishop, rook or queen slides in; sets count. */
static inline const int *slideDirs(int type, int &count) {
    count = type == QUEEN ? 8 : 4;
    return type == BISHOP ? BISHOP_DIRS : type == ROOK ? ROOK_DIRS : KING_DIRS;
}

static int board[120];
static int side;            // side to move
static int castling;        // CASTLE_* bits
static int epSquare;        // en passant target, 0 if none can be captured
static int halfmove;        // plies since the last capture or pawn move
static int kingSq[2];
static int pieceCount[13];
static uint64_t hashKey;
// Material plus piece-square score, kept up to date by every move.
// Positive is good for White. phase runs from 24 (all pieces) to 0.
static int psqMg, psqEg, phase;

// A move packs from, to, the promotion piece type and a flag.
enum { FLAG_NONE, FLAG_DOUBLE, FLAG_EP, FLAG_CASTLE };
static inline int makeMoveCode(int from, int to, int promo, int flag) {
    return from | (to << 7) | (promo << 14) | (flag << 17);
}
static inline int FROM(int m) { return m & 127; }
static inline int TO(int m) { return (m >> 7) & 127; }
static inline int PROMO(int m) { return (m >> 14) & 7; }
static inline int FLAG(int m) { return (m >> 17) & 3; }

// No piece has more than 27 moves (a queen in the centre; a pawn about to
// promote has at most 12), so 64 of them and two castling moves bound any
// board the protocol can describe, legal or not.
static const int MAX_MOVES = 64 * 27 + 2;

struct MoveList {
    int moves[MAX_MOVES];
    int scores[MAX_MOVES];
    int count = 0;
};

struct Undo {
    int move, captured, castling, epSquare, halfmove, psqMg, psqEg, phase;
    uint64_t hash;
};

static const int MAX_PLY = 96;
static const int MAX_GAME = 1024;
static Undo undoStack[MAX_PLY + 8];
static int undoTop = 0;
// Hashes of the positions before the current one: first the game history
// sent with BESTMOVE, then the moves made by the search. The root of the
// search is pushed at index rootRep.
static uint64_t repStack[MAX_GAME + MAX_PLY + 8];
static int repTop = 0;
static int rootRep = 0;

// ============================================================
//  Evaluation tables
// ============================================================

static const int MATERIAL_MG[6] = {100, 320, 330, 500, 900, 0};
static const int MATERIAL_EG[6] = {120, 310, 330, 520, 940, 0};
static const int PHASE_WEIGHT[6] = {0, 1, 1, 2, 4, 0};

// Piece-square tables from White's side, row 0 = rank 8. Black mirrors them.
// clang-format off
static const int PST_MG[6][64] = {
  { // pawn
      0,  0,  0,  0,  0,  0,  0,  0,
     50, 50, 50, 50, 50, 50, 50, 50,
     10, 10, 20, 30, 30, 20, 10, 10,
      5,  5, 10, 25, 25, 10,  5,  5,
      0,  0,  0, 20, 20,  0,  0,  0,
      5, -5,-10,  0,  0,-10, -5,  5,
      5, 10, 10,-20,-20, 10, 10,  5,
      0,  0,  0,  0,  0,  0,  0,  0 },
  { // knight
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50 },
  { // bishop
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20 },
  { // rook
      0,  0,  0,  0,  0,  0,  0,  0,
      5, 10, 10, 10, 10, 10, 10,  5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
      0,  0,  0,  5,  5,  0,  0,  0 },
  { // queen
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20 },
  { // king, middlegame: stay behind the pawns
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20 }
};

static const int PST_EG[6][64] = {
  { // pawn: advancing matters more than the file
      0,  0,  0,  0,  0,  0,  0,  0,
     60, 60, 60, 60, 60, 60, 60, 60,
     35, 35, 35, 35, 35, 35, 35, 35,
     20, 20, 20, 20, 20, 20, 20, 20,
     10, 10, 10, 10, 10, 10, 10, 10,
      5,  5,  5,  5,  5,  5,  5,  5,
      0,  0,  0,  0,  0,  0,  0,  0,
      0,  0,  0,  0,  0,  0,  0,  0 },
  { // knight
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50 },
  { // bishop
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20 },
  { // rook
      0,  0,  0,  0,  0,  0,  0,  0,
      0,  0,  0,  0,  0,  0,  0,  0,
      0,  0,  0,  0,  0,  0,  0,  0,
      0,  0,  0,  0,  0,  0,  0,  0,
      0,  0,  0,  0,  0,  0,  0,  0,
      0,  0,  0,  0,  0,  0,  0,  0,
      0,  0,  0,  0,  0,  0,  0,  0,
      0,  0,  0,  0,  0,  0,  0,  0 },
  { // queen
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
     -5,  0,  5,  5,  5,  5,  0, -5,
    -10,  0,  5,  5,  5,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20 },
  { // king, endgame: come to the centre
    -50,-30,-30,-30,-30,-30,-30,-50,
    -30,-10,-10,-10,-10,-10,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -50,-40,-30,-20,-20,-30,-40,-50 }
};
// clang-format on

// Evaluation weights (centipawns, middlegame / endgame)
static const int BISHOP_PAIR_MG = 30, BISHOP_PAIR_EG = 50;
static const int DOUBLED_MG = 8, DOUBLED_EG = 16;
static const int ISOLATED_MG = 12, ISOLATED_EG = 14;
// Passed pawn bonus by how far the pawn has come (index 1 = still at home)
static const int PASSED_MG[8] = {0, 0, 5, 10, 20, 35, 60, 0};
static const int PASSED_EG[8] = {0, 5, 10, 20, 40, 70, 120, 0};
static const int MOBILITY_BASE[6] = {0, 4, 6, 7, 13, 0};
static const int MOBILITY_MG[6] = {0, 4, 5, 2, 1, 0};
static const int MOBILITY_EG[6] = {0, 4, 5, 4, 2, 0};
static const int ROOK_OPEN_MG = 20, ROOK_OPEN_EG = 10;
static const int ROOK_SEMI_MG = 10, ROOK_SEMI_EG = 5;
static const int ROOK_SEVENTH_MG = 15, ROOK_SEVENTH_EG = 25;
static const int SHIELD_NEAR = 12, SHIELD_FAR = 6, SHIELD_MISSING = 10, KING_OPEN_FILE = 15;
static const int TEMPO = 10;

// pstMg/pstEg[piece][sq120]: material + table value, signed for the colour
static int pstMg[13][120], pstEg[13][120];
static int castleMask[120];
static bool aligned[120][120];  // same rank, file or diagonal
static int lmrTable[64][64];

static uint64_t zPiece[13][120], zSide, zCastle[16], zEp[8];

static uint64_t prngState = 0x123456789ABCDEFULL;
static uint64_t nextRandom() {
    prngState ^= (prngState << 13);
    prngState ^= (prngState >> 7);
    prngState ^= (prngState << 17);
    return prngState;
}

static void initTables() {
    for (int p = WP; p <= BK; p++)
        for (int r = 0; r < 8; r++)
            for (int c = 0; c < 8; c++)
                zPiece[p][SQ(r, c)] = nextRandom();
    zSide = nextRandom();
    for (int i = 0; i < 16; i++) zCastle[i] = nextRandom();
    for (int i = 0; i < 8; i++) zEp[i] = nextRandom();

    for (int p = WP; p <= BK; p++) {
        int type = typeOf(p);
        for (int r = 0; r < 8; r++) {
            for (int c = 0; c < 8; c++) {
                int idx = (colorOf(p) == WHITE ? r : 7 - r) * 8 + c;
                int sign = colorOf(p) == WHITE ? 1 : -1;
                pstMg[p][SQ(r, c)] = sign * (MATERIAL_MG[type] + PST_MG[type][idx]);
                pstEg[p][SQ(r, c)] = sign * (MATERIAL_EG[type] + PST_EG[type][idx]);
            }
        }
    }

    for (int i = 0; i < 120; i++) castleMask[i] = 15;
    castleMask[E1] = 15 & ~(CASTLE_WK | CASTLE_WQ);
    castleMask[H1] = 15 & ~CASTLE_WK;
    castleMask[A1] = 15 & ~CASTLE_WQ;
    castleMask[E8] = 15 & ~(CASTLE_BK | CASTLE_BQ);
    castleMask[H8] = 15 & ~CASTLE_BK;
    castleMask[A8] = 15 & ~CASTLE_BQ;

    for (int a = 0; a < 64; a++) {
        for (int b = 0; b < 64; b++) {
            int ar = a / 8, ac = a % 8, br = b / 8, bc = b % 8;
            aligned[SQ(ar, ac)][SQ(br, bc)] =
                ar == br || ac == bc || abs(ar - br) == abs(ac - bc);
        }
    }

    for (int d = 1; d < 64; d++)
        for (int n = 1; n < 64; n++)
            lmrTable[d][n] = static_cast<int>(0.75 + log(d) * log(n) / 2.25);
}

// ============================================================
//  Position set-up and updates
// ============================================================

static inline void addPiece(int piece, int sq) {
    board[sq] = piece;
    hashKey ^= zPiece[piece][sq];
    psqMg += pstMg[piece][sq];
    psqEg += pstEg[piece][sq];
    phase += PHASE_WEIGHT[typeOf(piece)];
    pieceCount[piece]++;
    if (piece == WK) kingSq[WHITE] = sq;
    else if (piece == BK) kingSq[BLACK] = sq;
}

static inline void removePiece(int sq) {
    int piece = board[sq];
    board[sq] = EMPTY;
    hashKey ^= zPiece[piece][sq];
    psqMg -= pstMg[piece][sq];
    psqEg -= pstEg[piece][sq];
    phase -= PHASE_WEIGHT[typeOf(piece)];
    pieceCount[piece]--;
}

static void clearBoard() {
    for (int i = 0; i < 120; i++) board[i] = OFFBOARD;
    for (int r = 0; r < 8; r++)
        for (int c = 0; c < 8; c++) board[SQ(r, c)] = EMPTY;
    memset(pieceCount, 0, sizeof(pieceCount));
    side = WHITE;
    castling = 0;
    epSquare = 0;
    halfmove = 0;
    kingSq[WHITE] = kingSq[BLACK] = 0;
    hashKey = 0;
    psqMg = psqEg = phase = 0;
    undoTop = 0;
    repTop = 0;
    rootRep = 0;
}

static int pieceFromChar(char ch) {
    const char *p = strchr(PIECE_CHARS, ch);
    return (p && ch != '\0') ? static_cast<int>(p - PIECE_CHARS) : -1;
}

/**
 * Finish loading: side, castling rights and en passant square.
 * A castling right only counts while king and rook are at home, and an en
 * passant square only if the pawn that double-stepped is there and one of
 * the mover's pawns stands beside it. The hash follows the same rule, so a
 * position reached again compares equal.
 */
static void finishSetup(int turn, const string &rights, int epRow, int epCol) {
    // A second king of the same colour is not chess; keep the first one.
    kingSq[WHITE] = kingSq[BLACK] = 0;
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            int p = board[SQ(r, c)];
            if (p == WK && !kingSq[WHITE]) kingSq[WHITE] = SQ(r, c);
            if (p == BK && !kingSq[BLACK]) kingSq[BLACK] = SQ(r, c);
        }
    }

    side = turn;
    castling = 0;
    for (char ch : rights) {
        if (ch == 'K' && board[E1] == WK && board[H1] == WR) castling |= CASTLE_WK;
        else if (ch == 'Q' && board[E1] == WK && board[A1] == WR) castling |= CASTLE_WQ;
        else if (ch == 'k' && board[E8] == BK && board[H8] == BR) castling |= CASTLE_BK;
        else if (ch == 'q' && board[E8] == BK && board[A8] == BR) castling |= CASTLE_BQ;
    }

    epSquare = 0;
    if (epCol >= 0 && epCol < 8 && epRow == (side == WHITE ? 2 : 5)) {
        int target = SQ(epRow, epCol);
        int pawnSq = target + (side == WHITE ? 10 : -10);
        int mine = side == WHITE ? WP : BP, theirs = side == WHITE ? BP : WP;
        if (board[target] == EMPTY && board[pawnSq] == theirs &&
            (board[pawnSq - 1] == mine || board[pawnSq + 1] == mine))
            epSquare = target;
    }

    if (side == BLACK) hashKey ^= zSide;
    hashKey ^= zCastle[castling];
    if (epSquare) hashKey ^= zEp[colOf(epSquare)];
}

/** Load a position from the protocol fields. Returns false on bad input. */
static bool loadPosition(const string &b, const string &rights, int turn,
                         int epRow, int epCol) {
    if (b.length() != 64) return false;
    clearBoard();
    for (int i = 0; i < 64; i++) {
        int piece = pieceFromChar(b[i]);
        if (piece < 0) return false;
        if (piece != EMPTY) addPiece(piece, SQ(i / 8, i % 8));
    }
    finishSetup(turn, rights, epRow, epCol);
    return true;
}

static string serializeBoard() {
    string s;
    s.reserve(64);
    for (int r = 0; r < 8; r++)
        for (int c = 0; c < 8; c++) s += PIECE_CHARS[board[SQ(r, c)]];
    return s;
}

// ============================================================
//  Attacks
// ============================================================

/** Is the square attacked by any piece of colour `by`? */
static bool attacked(int sq, int by) {
    if (by == WHITE) {
        if (board[sq + 11] == WP || board[sq + 9] == WP) return true;
    } else {
        if (board[sq - 11] == BP || board[sq - 9] == BP) return true;
    }
    int knight = makePiece(by, KNIGHT), king = makePiece(by, KING);
    for (int d : KNIGHT_DIRS)
        if (board[sq + d] == knight) return true;
    for (int d : KING_DIRS)
        if (board[sq + d] == king) return true;
    int bishop = makePiece(by, BISHOP), rook = makePiece(by, ROOK), queen = makePiece(by, QUEEN);
    for (int d : BISHOP_DIRS) {
        int t = sq + d;
        while (board[t] == EMPTY) t += d;
        if (board[t] == bishop || board[t] == queen) return true;
    }
    for (int d : ROOK_DIRS) {
        int t = sq + d;
        while (board[t] == EMPTY) t += d;
        if (board[t] == rook || board[t] == queen) return true;
    }
    return false;
}

static inline bool inCheckNow() {
    return kingSq[side] && attacked(kingSq[side], side ^ 1);
}

// ============================================================
//  Move generation
// ============================================================

enum { PROMO_QUEEN_ONLY, PROMO_QUEEN_KNIGHT, PROMO_ALL };

static inline void addMove(MoveList &ml, int from, int to, int promo, int flag) {
    ml.moves[ml.count++] = makeMoveCode(from, to, promo, flag);
}

static void addPawnMove(MoveList &ml, int from, int to, int flag, int promoMode) {
    int row = rowOf(to);
    if (row == 0 || row == 7) {
        addMove(ml, from, to, QUEEN, flag);
        if (promoMode != PROMO_QUEEN_ONLY) addMove(ml, from, to, KNIGHT, flag);
        if (promoMode == PROMO_ALL) {
            addMove(ml, from, to, ROOK, flag);
            addMove(ml, from, to, BISHOP, flag);
        }
    } else {
        addMove(ml, from, to, 0, flag);
    }
}

/**
 * Pseudo-legal moves for the side to move: every rule except "do not leave
 * your own king in check", which the caller tests after making the move.
 * Castling is only generated when it is fully legal. With noisyOnly, only
 * captures and promotions are produced (for the quiescence search).
 */
static void generateMoves(MoveList &ml, bool noisyOnly, int promoMode) {
    ml.count = 0;
    int us = side, them = side ^ 1;
    int forward = us == WHITE ? -10 : 10;
    int startRow = us == WHITE ? 6 : 1;
    int promoFrom = us == WHITE ? 1 : 6;

    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            int from = SQ(r, c);
            int piece = board[from];
            if (piece == EMPTY || colorOf(piece) != us) continue;

            switch (typeOf(piece)) {
            case PAWN: {
                int to = from + forward;
                if (board[to] == EMPTY) {
                    if (!noisyOnly || r == promoFrom)
                        addPawnMove(ml, from, to, FLAG_NONE, promoMode);
                    if (!noisyOnly && r == startRow && board[to + forward] == EMPTY)
                        addMove(ml, from, to + forward, 0, FLAG_DOUBLE);
                }
                for (int side_step = -1; side_step <= 1; side_step += 2) {
                    to = from + forward + side_step;
                    int target = board[to];
                    if (target != EMPTY && target != OFFBOARD && colorOf(target) == them)
                        addPawnMove(ml, from, to, FLAG_NONE, promoMode);
                    else if (to == epSquare && epSquare)
                        addMove(ml, from, to, 0, FLAG_EP);
                }
                break;
            }
            case KNIGHT:
            case KING: {
                const int *dirs = typeOf(piece) == KNIGHT ? KNIGHT_DIRS : KING_DIRS;
                for (int i = 0; i < 8; i++) {
                    int to = from + dirs[i];
                    int target = board[to];
                    if (target == EMPTY) {
                        if (!noisyOnly) addMove(ml, from, to, 0, FLAG_NONE);
                    } else if (target != OFFBOARD && colorOf(target) == them) {
                        addMove(ml, from, to, 0, FLAG_NONE);
                    }
                }
                break;
            }
            default: {
                int count;
                const int *dirs = slideDirs(typeOf(piece), count);
                for (int i = 0; i < count; i++) {
                    int d = dirs[i];
                    int to = from + d;
                    while (board[to] == EMPTY) {
                        if (!noisyOnly) addMove(ml, from, to, 0, FLAG_NONE);
                        to += d;
                    }
                    if (board[to] != OFFBOARD && colorOf(board[to]) == them)
                        addMove(ml, from, to, 0, FLAG_NONE);
                }
                break;
            }
            }
        }
    }

    if (noisyOnly) return;

    // Castling: right held, rook at home, squares between empty, and the
    // king neither in check nor passing over or landing on an attacked square.
    if (us == WHITE && board[E1] == WK) {
        if ((castling & CASTLE_WK) && board[H1] == WR && board[F1] == EMPTY && board[G1] == EMPTY &&
            !attacked(E1, BLACK) && !attacked(F1, BLACK) && !attacked(G1, BLACK))
            addMove(ml, E1, G1, 0, FLAG_CASTLE);
        if ((castling & CASTLE_WQ) && board[A1] == WR && board[D1] == EMPTY && board[C1] == EMPTY &&
            board[B1] == EMPTY && !attacked(E1, BLACK) && !attacked(D1, BLACK) && !attacked(C1, BLACK))
            addMove(ml, E1, C1, 0, FLAG_CASTLE);
    } else if (us == BLACK && board[E8] == BK) {
        if ((castling & CASTLE_BK) && board[H8] == BR && board[F8] == EMPTY && board[G8] == EMPTY &&
            !attacked(E8, WHITE) && !attacked(F8, WHITE) && !attacked(G8, WHITE))
            addMove(ml, E8, G8, 0, FLAG_CASTLE);
        if ((castling & CASTLE_BQ) && board[A8] == BR && board[D8] == EMPTY && board[C8] == EMPTY &&
            board[B8] == EMPTY && !attacked(E8, WHITE) && !attacked(D8, WHITE) && !attacked(C8, WHITE))
            addMove(ml, E8, C8, 0, FLAG_CASTLE);
    }
}

// ============================================================
//  Make / unmake: the only place where the position changes
// ============================================================

static void makeMove(int m) {
    Undo &u = undoStack[undoTop++];
    u.move = m;
    u.castling = castling;
    u.epSquare = epSquare;
    u.halfmove = halfmove;
    u.psqMg = psqMg;
    u.psqEg = psqEg;
    u.phase = phase;
    u.hash = hashKey;
    repStack[repTop++] = hashKey;

    int from = FROM(m), to = TO(m), promo = PROMO(m), flag = FLAG(m);
    int piece = board[from];
    int captured = board[to];

    if (epSquare) hashKey ^= zEp[colOf(epSquare)];
    hashKey ^= zCastle[castling];
    halfmove++;

    if (flag == FLAG_EP) {
        int capSq = to + (side == WHITE ? 10 : -10);
        captured = board[capSq];
        removePiece(capSq);
    } else if (captured != EMPTY) {
        removePiece(to);
    }
    u.captured = captured;
    if (captured != EMPTY || typeOf(piece) == PAWN) halfmove = 0;

    removePiece(from);
    addPiece(promo ? makePiece(side, promo) : piece, to);

    if (flag == FLAG_CASTLE) {
        int rookFrom = to > from ? to + 1 : to - 2;
        int rookTo = to > from ? to - 1 : to + 1;
        int rook = board[rookFrom];
        removePiece(rookFrom);
        addPiece(rook, rookTo);
    }

    castling &= castleMask[from] & castleMask[to];
    epSquare = 0;
    if (flag == FLAG_DOUBLE) {
        int enemyPawn = side == WHITE ? BP : WP;
        if (board[to - 1] == enemyPawn || board[to + 1] == enemyPawn)
            epSquare = (from + to) / 2;
    }
    hashKey ^= zCastle[castling];
    if (epSquare) hashKey ^= zEp[colOf(epSquare)];

    side ^= 1;
    hashKey ^= zSide;
}

static void unmakeMove() {
    Undo &u = undoStack[--undoTop];
    repTop--;
    side ^= 1;

    int m = u.move;
    int from = FROM(m), to = TO(m), flag = FLAG(m);

    if (flag == FLAG_CASTLE) {
        int rookFrom = to > from ? to + 1 : to - 2;
        int rookTo = to > from ? to - 1 : to + 1;
        int rook = board[rookTo];
        removePiece(rookTo);
        addPiece(rook, rookFrom);
    }

    int piece = board[to];
    removePiece(to);
    addPiece(PROMO(m) ? makePiece(side, PAWN) : piece, from);

    if (u.captured != EMPTY) {
        int capSq = flag == FLAG_EP ? to + (side == WHITE ? 10 : -10) : to;
        addPiece(u.captured, capSq);
    }

    castling = u.castling;
    epSquare = u.epSquare;
    halfmove = u.halfmove;
    psqMg = u.psqMg;
    psqEg = u.psqEg;
    phase = u.phase;
    hashKey = u.hash;
}

/** Pass the turn (used by null-move pruning only). */
static void makeNull() {
    Undo &u = undoStack[undoTop++];
    u.epSquare = epSquare;
    u.halfmove = halfmove;
    u.hash = hashKey;
    repStack[repTop++] = hashKey;
    if (epSquare) hashKey ^= zEp[colOf(epSquare)];
    epSquare = 0;
    halfmove = 0;  // a repetition cannot reach across a pass
    side ^= 1;
    hashKey ^= zSide;
}

static void unmakeNull() {
    Undo &u = undoStack[--undoTop];
    repTop--;
    side ^= 1;
    epSquare = u.epSquare;
    halfmove = u.halfmove;
    hashKey = u.hash;
}

/** Make the move if it is legal. Returns false (and changes nothing) if not. */
static bool makeIfLegal(int m) {
    makeMove(m);
    if (kingSq[side ^ 1] && attacked(kingSq[side ^ 1], side)) {
        unmakeMove();
        return false;
    }
    return true;
}

/** All legal moves of the side to move. */
static void generateLegal(MoveList &legal, int promoMode) {
    MoveList ml;
    generateMoves(ml, false, promoMode);
    legal.count = 0;
    for (int i = 0; i < ml.count; i++) {
        if (makeIfLegal(ml.moves[i])) {
            unmakeMove();
            legal.moves[legal.count++] = ml.moves[i];
        }
    }
}

static bool hasLegalMove() {
    MoveList ml;
    generateMoves(ml, false, PROMO_QUEEN_ONLY);
    for (int i = 0; i < ml.count; i++) {
        if (makeIfLegal(ml.moves[i])) {
            unmakeMove();
            return true;
        }
    }
    return false;
}

static inline bool isCapture(int m) {
    return board[TO(m)] != EMPTY || FLAG(m) == FLAG_EP;
}

/**
 * Checks if the current board state is a draw due to insufficient material.
 * Cases: K vs K, K+N vs K, and kings with any number of bishops that all
 * stand on squares of one colour (K+B vs K, K+B vs K+B same colour).
 */
static bool isInsufficientMaterial() {
    if (pieceCount[WP] || pieceCount[BP] || pieceCount[WR] || pieceCount[BR] ||
        pieceCount[WQ] || pieceCount[BQ])
        return false;
    int knights = pieceCount[WN] + pieceCount[BN];
    int bishops = pieceCount[WB] + pieceCount[BB];
    if (knights == 0) {
        if (bishops <= 1) return true;
        int light = 0, dark = 0;
        for (int r = 0; r < 8; r++)
            for (int c = 0; c < 8; c++)
                if (typeOf(board[SQ(r, c)]) == BISHOP && board[SQ(r, c)] != EMPTY)
                    ((r + c) % 2 == 0 ? light : dark)++;
        return light == 0 || dark == 0;
    }
    // A single knight draws only against a bare king
    return knights == 1 && bishops == 0;
}

static uint64_t perft(int depth) {
    MoveList ml;
    generateMoves(ml, false, PROMO_ALL);
    uint64_t nodes = 0;
    for (int i = 0; i < ml.count; i++) {
        if (!makeIfLegal(ml.moves[i])) continue;
        nodes += depth <= 1 ? 1 : perft(depth - 1);
        unmakeMove();
    }
    return nodes;
}

// ============================================================
//  Static evaluation
// ============================================================

/** Distance of a square from the four centre squares, 0 to 6. */
static inline int centreDistance(int sq) {
    int r = rowOf(sq), c = colOf(sq);
    return max(3 - r, r - 4) + max(3 - c, c - 4);
}

/**
 * Static evaluation of the current board in centipawns.
 * Positive => white advantage, negative => black advantage.
 *
 * Material and piece-square tables (kept incrementally), bishop pair,
 * mobility, pawn structure (doubled, isolated, passed), rooks on open
 * files and on the seventh rank, pawn shelter of the king, and for bare
 * endgames a term that drives the losing king to the edge. Middlegame and
 * endgame scores are blended by the material left on the board.
 */
static int evaluate() {
    if (isInsufficientMaterial()) return 0;

    int mg = psqMg, eg = psqEg;

    // Pawns per file; index 0 and 9 stand for the files beside a and h.
    // blackRear / whiteRear: per file the row of the pawn nearest its own
    // side. A white pawn is passed when no black pawn on its own or a
    // neighbouring file stands on a row in front of it.
    int pawns[2][10] = {{0}, {0}};
    int blackRear[10], whiteRear[10];
    for (int f = 0; f < 10; f++) { blackRear[f] = 8; whiteRear[f] = -1; }
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            int p = board[SQ(r, c)];
            if (p == WP) {
                pawns[WHITE][c + 1]++;
                if (r > whiteRear[c + 1]) whiteRear[c + 1] = r;
            } else if (p == BP) {
                pawns[BLACK][c + 1]++;
                if (r < blackRear[c + 1]) blackRear[c + 1] = r;
            }
        }
    }

    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            int sq = SQ(r, c);
            int piece = board[sq];
            if (piece == EMPTY) continue;
            int us = colorOf(piece), them = us ^ 1;
            int type = typeOf(piece);
            int sign = us == WHITE ? 1 : -1;
            int f = c + 1;

            if (type == PAWN) {
                if (pawns[us][f] > 1) { mg -= sign * DOUBLED_MG; eg -= sign * DOUBLED_EG; }
                if (!pawns[us][f - 1] && !pawns[us][f + 1]) {
                    mg -= sign * ISOLATED_MG;
                    eg -= sign * ISOLATED_EG;
                }
                bool passed;
                int advance;  // 1 on the home row .. 6 one step from promotion
                if (us == WHITE) {
                    passed = blackRear[f - 1] >= r && blackRear[f] >= r && blackRear[f + 1] >= r;
                    advance = 7 - r;
                } else {
                    passed = whiteRear[f - 1] <= r && whiteRear[f] <= r && whiteRear[f + 1] <= r;
                    advance = r;
                }
                if (passed) { mg += sign * PASSED_MG[advance]; eg += sign * PASSED_EG[advance]; }
                continue;
            }

            if (type == KING) {
                // Pawn shelter, only while the king is on its two home rows
                int homeRow = us == WHITE ? 7 : 0;
                if (abs(r - homeRow) <= 1) {
                    int ahead = us == WHITE ? -10 : 10;
                    int pawn = makePiece(us, PAWN);
                    int shelter = 0;
                    for (int kc = max(0, c - 1); kc <= min(7, c + 1); kc++) {
                        int s = SQ(r, kc);
                        if (board[s + ahead] == pawn) shelter += SHIELD_NEAR;
                        else if (board[s + 2 * ahead] == pawn) shelter += SHIELD_FAR;
                        else {
                            shelter -= SHIELD_MISSING;
                            if (!pawns[us][kc + 1]) shelter -= KING_OPEN_FILE;
                        }
                    }
                    mg += sign * shelter;
                }
                continue;
            }

            // Mobility: squares the piece can move to
            int mobility = 0;
            if (type == KNIGHT) {
                for (int d : KNIGHT_DIRS) {
                    int t = board[sq + d];
                    if (t == EMPTY || (t != OFFBOARD && colorOf(t) == them)) mobility++;
                }
            } else {
                int count;
                const int *dirs = slideDirs(type, count);
                for (int i = 0; i < count; i++) {
                    int d = dirs[i];
                    int t = sq + d;
                    while (board[t] == EMPTY) { mobility++; t += d; }
                    if (board[t] != OFFBOARD && colorOf(board[t]) == them) mobility++;
                }
            }
            mg += sign * MOBILITY_MG[type] * (mobility - MOBILITY_BASE[type]);
            eg += sign * MOBILITY_EG[type] * (mobility - MOBILITY_BASE[type]);

            if (type == ROOK) {
                if (!pawns[us][f]) {
                    if (!pawns[them][f]) { mg += sign * ROOK_OPEN_MG; eg += sign * ROOK_OPEN_EG; }
                    else { mg += sign * ROOK_SEMI_MG; eg += sign * ROOK_SEMI_EG; }
                }
                // On the seventh with the enemy king cut off on the eighth
                int seventh = us == WHITE ? 1 : 6;
                int eighth = us == WHITE ? 0 : 7;
                if (r == seventh && kingSq[them] && rowOf(kingSq[them]) == eighth) {
                    mg += sign * ROOK_SEVENTH_MG;
                    eg += sign * ROOK_SEVENTH_EG;
                }
            }
        }
    }

    if (pieceCount[WB] >= 2) { mg += BISHOP_PAIR_MG; eg += BISHOP_PAIR_EG; }
    if (pieceCount[BB] >= 2) { mg -= BISHOP_PAIR_MG; eg -= BISHOP_PAIR_EG; }

    // Endgame knowledge
    int material[2];
    for (int s = 0; s < 2; s++) {
        material[s] = 0;
        for (int t = PAWN; t <= QUEEN; t++)
            material[s] += pieceCount[makePiece(s, t)] * MATERIAL_EG[t];
    }
    int strong = material[WHITE] >= material[BLACK] ? WHITE : BLACK;
    int weak = strong ^ 1;
    int lead = material[strong] - material[weak];
    int strongSign = strong == WHITE ? 1 : -1;
    bool strongHasPawns = pieceCount[makePiece(strong, PAWN)] > 0;
    bool weakHasPawns = pieceCount[makePiece(weak, PAWN)] > 0;

    if (!strongHasPawns && !weakHasPawns && material[weak] == 0 &&
        pieceCount[makePiece(strong, KNIGHT)] == 2 && material[strong] == 2 * MATERIAL_EG[KNIGHT]) {
        return 0;  // two knights cannot force mate
    }
    if (lead >= 400 && !weakHasPawns && material[weak] <= MATERIAL_EG[BISHOP] &&
        kingSq[WHITE] && kingSq[BLACK]) {
        // Winning material against a nearly bare king: push that king to
        // the edge and bring our own king up.
        int kingsApart = abs(rowOf(kingSq[WHITE]) - rowOf(kingSq[BLACK])) +
                         abs(colOf(kingSq[WHITE]) - colOf(kingSq[BLACK]));
        eg += strongSign * (10 * centreDistance(kingSq[weak]) + 4 * (14 - kingsApart));
    } else if (!strongHasPawns && !weakHasPawns && lead < 400) {
        // Without pawns a small material lead rarely wins (R v B, R+B v R)
        mg /= 4;
        eg /= 4;
    }

    int p = phase > 24 ? 24 : phase;
    int score = (mg * p + eg * (24 - p)) / 24;
    return score + (side == WHITE ? TEMPO : -TEMPO);
}

static inline int evalForSide() {
    int e = evaluate();
    return side == WHITE ? e : -e;
}

// ============================================================
//  Search
// ============================================================

static const int INF = 32000;
static const int MATE = 31000;
static const int MATE_BOUND = MATE - 512;  // scores beyond this are forced mates
static const int MAX_DEPTH = 64;

// Pruning margins in centipawns. A node this far above beta at the given
// depth is not searched (reverse futility); a quiet move this far below
// alpha is not either (futility).
static const int RFP_MAX_DEPTH = 3, RFP_MARGIN_PER_PLY = 120;
static const int FUTILITY_MAX_DEPTH = 2, FUTILITY_MARGIN = 100, FUTILITY_MARGIN_PER_PLY = 100;
// Null move: tried from this depth, searched this much shallower
static const int NULL_MIN_DEPTH = 3;
static inline int nullReduction(int depth) { return 2 + depth / 4; }
// Quiescence: a capture whose gain plus this margin cannot reach alpha is
// skipped, and a promotion counts as gaining this much on top
static const int DELTA_MARGIN = 200, PROMOTION_GAIN = 800;
// Aspiration window around the last score, from this depth; it doubles on
// every failure and is given up once it is wider than the limit
static const int ASPIRATION_MIN_DEPTH = 4, ASPIRATION_WINDOW = 40, ASPIRATION_LIMIT = 600;
// History scores are halved once one of them passes this
static const int HISTORY_LIMIT = 1 << 20;
// Percentage of the time limit the main search may use when alternatives
// are wanted as well. Each of them is a full-window search at the final
// depth and costs about as much as the main search's last iteration.
static const int MAIN_SHARE_WITH_ALTS = 50;

enum { BOUND_NONE, BOUND_EXACT, BOUND_LOWER, BOUND_UPPER };

struct TTEntry {
    uint64_t key;
    int32_t move;
    int16_t score;
    int8_t depth;
    uint8_t bound;
};

// Two entries per slot: the first keeps the deepest search of the slot,
// the second is always replaced.
static const int TT_SLOTS = 1 << 19;
static TTEntry transpositionTable[TT_SLOTS * 2];

static std::chrono::steady_clock::time_point startTime;
static long long deadlineMs = -1;  // hard stop, measured from startTime
static bool searchAborted = false;
static long long nodesSearched = 0;
static long long tthits = 0;
static int killers[MAX_PLY + 2][2];
static int historyTable[13][120];

static long long elapsedMs() {
    auto now = std::chrono::steady_clock::now();
    return std::chrono::duration_cast<std::chrono::milliseconds>(now - startTime).count();
}

static inline void countNode() {
    if ((++nodesSearched & 1023) == 0 && deadlineMs >= 0 && elapsedMs() >= deadlineMs)
        searchAborted = true;
}

// Mate scores are stored relative to the node, not to the root, so an
// entry is still right when the position is reached at another depth.
static inline int scoreToTT(int score, int ply) {
    if (score >= MATE_BOUND) return score + ply;
    if (score <= -MATE_BOUND) return score - ply;
    return score;
}
static inline int scoreFromTT(int score, int ply) {
    if (score >= MATE_BOUND) return score - ply;
    if (score <= -MATE_BOUND) return score + ply;
    return score;
}

static TTEntry *probeTT(uint64_t key) {
    TTEntry *slot = &transpositionTable[(key & (TT_SLOTS - 1)) * 2];
    if (slot[0].key == key && slot[0].bound != BOUND_NONE) return &slot[0];
    if (slot[1].key == key && slot[1].bound != BOUND_NONE) return &slot[1];
    return nullptr;
}

static void storeTT(uint64_t key, int move, int score, int depth, int bound, int ply) {
    TTEntry *slot = &transpositionTable[(key & (TT_SLOTS - 1)) * 2];
    TTEntry *e;
    if (slot[0].key == key || slot[0].bound == BOUND_NONE || depth >= slot[0].depth) {
        if (slot[0].key != key && slot[0].bound != BOUND_NONE) slot[1] = slot[0];
        e = &slot[0];
    } else {
        e = &slot[1];
    }
    if (move == 0 && e->key == key) move = e->move;  // keep the known best move
    e->key = key;
    e->move = move;
    e->score = static_cast<int16_t>(scoreToTT(score, ply));
    e->depth = static_cast<int8_t>(depth);
    e->bound = static_cast<uint8_t>(bound);
}

/**
 * Does the search score the current position as a draw by repetition? It
 * does when the position occurred before on the line being searched, after
 * the root. An occurrence in the game itself (the root included) is real,
 * so it takes two of those, a threefold repetition.
 */
static bool isRepetition() {
    int limit = halfmove < repTop ? halfmove : repTop;
    int inGame = 0;
    for (int back = 2; back <= limit; back += 2) {
        int i = repTop - back;
        if (repStack[i] != hashKey) continue;
        if (i > rootRep || ++inGame == 2) return true;
    }
    return false;
}

static inline bool hasNonPawnMaterial(int s) {
    return pieceCount[makePiece(s, KNIGHT)] || pieceCount[makePiece(s, BISHOP)] ||
           pieceCount[makePiece(s, ROOK)] || pieceCount[makePiece(s, QUEEN)];
}

// Knight and bishop count the same here, so that bishop takes knight
// (or the reverse) is an even trade and not a loss of ten points.
static const int SEE_VALUE[6] = {100, 325, 325, 500, 900, 20000};

/** The least valuable piece of colour `by` that attacks sq, or 0. */
static int leastAttacker(int sq, int by) {
    int pawn = makePiece(by, PAWN);
    if (by == WHITE) {
        if (board[sq + 11] == pawn) return sq + 11;
        if (board[sq + 9] == pawn) return sq + 9;
    } else {
        if (board[sq - 11] == pawn) return sq - 11;
        if (board[sq - 9] == pawn) return sq - 9;
    }
    int knight = makePiece(by, KNIGHT);
    for (int d : KNIGHT_DIRS)
        if (board[sq + d] == knight) return sq + d;
    int best = 0, bestType = KING + 1;
    int king = makePiece(by, KING), queen = makePiece(by, QUEEN);
    for (int d : KING_DIRS)
        if (board[sq + d] == king) { best = sq + d; bestType = KING; }
    // Diagonals before lines, as in main.py: with two queens attacking, the
    // one taken first decides what is uncovered behind it.
    for (int slider : {BISHOP, ROOK}) {
        int count;
        const int *dirs = slideDirs(slider, count);
        int piece = makePiece(by, slider);
        for (int i = 0; i < count; i++) {
            int t = sq + dirs[i];
            while (board[t] == EMPTY) t += dirs[i];
            if (board[t] == piece && slider < bestType) { best = t; bestType = slider; }
            else if (board[t] == queen && QUEEN < bestType) { best = t; bestType = QUEEN; }
        }
    }
    return best;
}

/**
 * Static exchange evaluation: the material balance of the capture
 * sequence on the target square if both sides keep recapturing with their
 * least valuable piece and stop when it no longer pays.
 */
static int see(int m) {
    int from = FROM(m), to = TO(m);
    int gain[32];
    int removedSq[32], removedPiece[32];
    int n = 0, removed = 0;

    int target = board[to];
    if (FLAG(m) == FLAG_EP) {
        int capSq = to + (side == WHITE ? 10 : -10);
        removedSq[removed] = capSq; removedPiece[removed++] = board[capSq];
        board[capSq] = EMPTY;
        gain[0] = SEE_VALUE[PAWN];
    } else {
        gain[0] = target == EMPTY ? 0 : SEE_VALUE[typeOf(target)];
    }
    int onSquare = SEE_VALUE[typeOf(board[from])];  // value now standing on `to`
    if (PROMO(m)) {
        gain[0] += SEE_VALUE[PROMO(m)] - SEE_VALUE[PAWN];
        onSquare = SEE_VALUE[PROMO(m)];
    }
    removedSq[removed] = from; removedPiece[removed++] = board[from];
    board[from] = EMPTY;

    int by = side ^ 1;
    while (n < 30) {
        int attacker = leastAttacker(to, by);
        if (!attacker) break;
        n++;
        gain[n] = onSquare - gain[n - 1];
        onSquare = SEE_VALUE[typeOf(board[attacker])];
        removedSq[removed] = attacker; removedPiece[removed++] = board[attacker];
        board[attacker] = EMPTY;
        by ^= 1;
    }
    for (int i = removed - 1; i >= 0; i--) board[removedSq[i]] = removedPiece[i];

    while (n > 0) {
        gain[n - 1] = -max(-gain[n - 1], gain[n]);
        n--;
    }
    return gain[0];
}

static const int SCORE_TT = 1 << 30;
static const int SCORE_GOOD_CAPTURE = 1 << 24;
static const int SCORE_KILLER = 1 << 22;
static const int SCORE_BAD_CAPTURE = -(1 << 24);
// Orders a queen promotion ahead of any capture but that of a queen
static const int SCORE_QUEEN_PROMOTION = 7000;

/** Type of the piece the move captures, -1 if none. */
static inline int victimType(int m) {
    if (FLAG(m) == FLAG_EP) return PAWN;
    return board[TO(m)] == EMPTY ? -1 : typeOf(board[TO(m)]);
}

/** Give every move an ordering score: best candidates first. */
static void scoreMoves(MoveList &ml, int ttMove, int ply) {
    for (int i = 0; i < ml.count; i++) {
        int m = ml.moves[i];
        int score;
        if (m == ttMove) {
            score = SCORE_TT;
        } else if (isCapture(m) || PROMO(m)) {
            int victim = victimType(m);
            int attacker = typeOf(board[FROM(m)]);
            // Most valuable victim first, least valuable attacker first
            int mvvLva = (victim >= 0 ? SEE_VALUE[victim] : 0) * 8 - SEE_VALUE[attacker] / 100;
            if (PROMO(m) == QUEEN) mvvLva += SCORE_QUEEN_PROMOTION;
            // A capture that may lose material is checked exactly
            bool risky = victim < 0 || SEE_VALUE[victim] < SEE_VALUE[attacker];
            if (risky && PROMO(m) != QUEEN && see(m) < 0) score = SCORE_BAD_CAPTURE + mvvLva;
            else score = SCORE_GOOD_CAPTURE + mvvLva;
        } else if (ply >= 0 && m == killers[ply][0]) {
            score = SCORE_KILLER;
        } else if (ply >= 0 && m == killers[ply][1]) {
            score = SCORE_KILLER - 1;
        } else {
            score = historyTable[board[FROM(m)]][TO(m)];
        }
        ml.scores[i] = score;
    }
}

/**
 * Bring the best remaining move to position i. Moves that score the same
 * keep the order they were generated in, as with the stable sort in
 * main.py; a swap would reorder them and the two engines would search
 * different trees.
 */
static inline void pickMove(MoveList &ml, int i) {
    int best = i;
    for (int j = i + 1; j < ml.count; j++)
        if (ml.scores[j] > ml.scores[best]) best = j;
    if (best != i) {
        rotate(ml.moves + i, ml.moves + best, ml.moves + best + 1);
        rotate(ml.scores + i, ml.scores + best, ml.scores + best + 1);
    }
}

/**
 * Quiescence search: play out captures and promotions (and every reply
 * while in check) until the position is quiet, so that the static
 * evaluation is never taken in the middle of an exchange.
 */
static int quiesce(int alpha, int beta, int ply, bool inCheck) {
    if (searchAborted) return 0;
    countNode();
    if (ply >= MAX_PLY - 1) return evalForSide();

    int best = -INF;
    int standPat = -INF;
    if (!inCheck) {
        standPat = evalForSide();
        if (standPat >= beta) return standPat;
        if (standPat > alpha) alpha = standPat;
        best = standPat;
    }

    MoveList ml;
    generateMoves(ml, !inCheck, PROMO_QUEEN_ONLY);
    scoreMoves(ml, 0, -1);

    int legal = 0;
    for (int i = 0; i < ml.count; i++) {
        pickMove(ml, i);
        int m = ml.moves[i];
        if (!inCheck) {
            // Losing captures are not worth following, and neither is a
            // capture that cannot bring the score back up to alpha.
            if (ml.scores[i] < 0) break;
            int victim = victimType(m);
            int gain = (victim >= 0 ? SEE_VALUE[victim] : 0) + (PROMO(m) ? PROMOTION_GAIN : 0);
            if (standPat + gain + DELTA_MARGIN <= alpha) continue;
        }
        if (!makeIfLegal(m)) continue;
        legal++;
        int score = -quiesce(-beta, -alpha, ply + 1, inCheckNow());
        unmakeMove();
        if (searchAborted) return 0;
        if (score > best) {
            best = score;
            if (score > alpha) {
                alpha = score;
                if (alpha >= beta) break;
            }
        }
    }

    if (inCheck && legal == 0) return -MATE + ply;
    return best;
}

/**
 * Principal variation search (negamax alpha-beta).
 *
 *   depth      : remaining plies to search
 *   alpha/beta : window, from the point of view of the side to move
 *   ply        : distance from the root
 *   inCheck    : the side to move is in check
 *   nullOk     : a null move may be tried here
 *
 * Returns the score for the side to move.
 */
static int search(int depth, int alpha, int beta, int ply, bool inCheck, bool nullOk) {
    if (searchAborted) return 0;

    bool pvNode = beta - alpha > 1;

    // Draws: repetition, dead position, fifty-move rule (mate comes first)
    if (isRepetition() || isInsufficientMaterial()) return 0;
    if (halfmove >= 100 && (!inCheck || hasLegalMove())) return 0;

    // A shorter mate found elsewhere makes this line pointless
    alpha = max(alpha, -MATE + ply);
    beta = min(beta, MATE - ply - 1);
    if (alpha >= beta) return alpha;

    if (ply >= MAX_PLY - 1) return evalForSide();

    if (inCheck) depth++;  // never stop while in check
    if (depth <= 0) return quiesce(alpha, beta, ply, false);

    countNode();

    int ttMove = 0;
    TTEntry *entry = probeTT(hashKey);
    if (entry) {
        tthits++;
        ttMove = entry->move;
        if (!pvNode && entry->depth >= depth) {
            int score = scoreFromTT(entry->score, ply);
            if (entry->bound == BOUND_EXACT) return score;
            if (entry->bound == BOUND_LOWER && score >= beta) return score;
            if (entry->bound == BOUND_UPPER && score <= alpha) return score;
        }
    }

    int staticEval = inCheck ? -INF : evalForSide();

    if (!pvNode && !inCheck && abs(beta) < MATE_BOUND) {
        // Reverse futility: far above beta close to the horizon
        if (depth <= RFP_MAX_DEPTH && staticEval - RFP_MARGIN_PER_PLY * depth >= beta)
            return staticEval;

        // Null move: if passing still holds beta, a real move will too.
        // Not with only pawns left, where having to move can be a loss.
        if (nullOk && depth >= NULL_MIN_DEPTH && staticEval >= beta && hasNonPawnMaterial(side)) {
            makeNull();
            int score = -search(depth - 1 - nullReduction(depth), -beta, -beta + 1, ply + 1, false, false);
            unmakeNull();
            if (searchAborted) return 0;
            if (score >= beta) return score >= MATE_BOUND ? beta : score;
        }
    }

    MoveList ml;
    generateMoves(ml, false, PROMO_QUEEN_KNIGHT);
    scoreMoves(ml, ttMove, ply);

    int originalAlpha = alpha;
    int bestScore = -INF;
    int bestMove = 0;
    int legal = 0;
    int us = side;

    for (int i = 0; i < ml.count; i++) {
        pickMove(ml, i);
        int m = ml.moves[i];
        int from = FROM(m);
        int piece = board[from];
        bool quiet = !isCapture(m) && !PROMO(m);

        // Only a king move, an en passant capture or a piece on a line
        // with the king can expose the king when it is not in check.
        bool mustVerify = inCheck || typeOf(piece) == KING || FLAG(m) == FLAG_EP ||
                          aligned[from][kingSq[us]];
        makeMove(m);
        if (mustVerify && kingSq[us] && attacked(kingSq[us], side)) {
            unmakeMove();
            continue;
        }
        legal++;
        bool givesCheck = inCheckNow();

        // Futility: a quiet move that cannot lift a hopeless position
        if (!pvNode && !inCheck && quiet && !givesCheck && legal > 1 && depth <= FUTILITY_MAX_DEPTH &&
            staticEval + FUTILITY_MARGIN + FUTILITY_MARGIN_PER_PLY * depth <= alpha &&
            abs(alpha) < MATE_BOUND) {
            unmakeMove();
            continue;
        }

        int score;
        int newDepth = depth - 1;
        if (legal == 1) {
            score = -search(newDepth, -beta, -alpha, ply + 1, givesCheck, true);
        } else {
            // Late move reduction: moves ordered far back are searched
            // shallower first and again at full depth only if they surprise.
            int reduction = 0;
            if (depth >= 3 && legal > (pvNode ? 5 : 3) && quiet && !inCheck && !givesCheck) {
                reduction = lmrTable[min(depth, 63)][min(legal, 63)];
                if (pvNode && reduction > 0) reduction--;
                if (reduction > newDepth - 1) reduction = max(0, newDepth - 1);
            }
            score = -search(newDepth - reduction, -alpha - 1, -alpha, ply + 1, givesCheck, true);
            if (score > alpha && reduction > 0)
                score = -search(newDepth, -alpha - 1, -alpha, ply + 1, givesCheck, true);
            if (score > alpha && score < beta)
                score = -search(newDepth, -beta, -alpha, ply + 1, givesCheck, true);
        }
        unmakeMove();
        if (searchAborted) return 0;

        if (score > bestScore) {
            bestScore = score;
            bestMove = m;
            if (score > alpha) {
                alpha = score;
                if (alpha >= beta) {
                    if (quiet) {
                        if (killers[ply][0] != m) {
                            killers[ply][1] = killers[ply][0];
                            killers[ply][0] = m;
                        }
                        int &h = historyTable[piece][TO(m)];
                        h += depth * depth;
                        if (h > HISTORY_LIMIT) {
                            for (auto &row : historyTable)
                                for (int &v : row) v /= 2;
                        }
                    }
                    break;
                }
            }
        }
    }

    if (legal == 0) return inCheck ? -MATE + ply : 0;  // checkmate or stalemate

    int bound = bestScore >= beta ? BOUND_LOWER
              : bestScore > originalAlpha ? BOUND_EXACT : BOUND_UPPER;
    storeTT(hashKey, bestMove, bestScore, depth, bound, ply);
    return bestScore;
}

/**
 * Search the root moves in the given order. Moves listed in `excluded`
 * are skipped (used to find the next best alternatives).
 * Returns the best score and sets bestMove; on abort the result is void.
 */
static int searchRoot(int depth, int alpha, int beta, vector<int> &rootMoves,
                      const vector<int> &excluded, int &bestMove) {
    int bestScore = -INF;
    bestMove = 0;
    int searched = 0;
    for (size_t i = 0; i < rootMoves.size(); i++) {
        int m = rootMoves[i];
        if (find(excluded.begin(), excluded.end(), m) != excluded.end()) continue;
        makeMove(m);
        bool givesCheck = inCheckNow();
        int score;
        if (searched == 0) {
            score = -search(depth - 1, -beta, -alpha, 1, givesCheck, true);
        } else {
            score = -search(depth - 1, -alpha - 1, -alpha, 1, givesCheck, true);
            if (score > alpha && score < beta)
                score = -search(depth - 1, -beta, -alpha, 1, givesCheck, true);
        }
        unmakeMove();
        if (searchAborted) return 0;
        searched++;
        if (score > bestScore) {
            bestScore = score;
            bestMove = m;
            if (score > alpha) {
                alpha = score;
                // Try the new best move first in the next iteration
                rotate(rootMoves.begin(), rootMoves.begin() + i, rootMoves.begin() + i + 1);
                if (alpha >= beta) break;
            }
        }
    }
    return bestScore;
}

/** Score as sent to the bridge: from White's side, mates near +-99999. */
static int reportScore(int score, int mover) {
    if (score >= MATE_BOUND) score = 99999 - (MATE - score);
    else if (score <= -MATE_BOUND) score = -99999 + (MATE + score);
    return mover == WHITE ? score : -score;
}

/**
 * BESTMOVE handler: iterative deepening with aspiration windows.
 * Stops at maxDepth or when the time is used up, and always answers with
 * the best move of the last iteration that was searched completely.
 */
static void handleBestMove(int maxDepth, long long timeLimitMs, int alternatives) {
    if (maxDepth < 1) maxDepth = 1;  // depth 0 would return an unsearched move
    if (maxDepth > MAX_DEPTH) maxDepth = MAX_DEPTH;
    if (alternatives < 0) alternatives = 0;

    startTime = std::chrono::steady_clock::now();
    searchAborted = false;
    nodesSearched = 0;
    tthits = 0;
    memset(transpositionTable, 0, sizeof(transpositionTable));
    memset(killers, 0, sizeof(killers));
    memset(historyTable, 0, sizeof(historyTable));
    rootRep = repTop;

    int mover = side;
    MoveList legal;
    generateLegal(legal, PROMO_QUEEN_ONLY);
    if (legal.count == 0) {
        cout << "BESTMOVE NONE" << endl;
        return;
    }

    // Order the root moves once: captures first, as in the tree
    scoreMoves(legal, 0, -1);
    vector<int> rootMoves;
    for (int i = 0; i < legal.count; i++) {
        pickMove(legal, i);
        rootMoves.push_back(legal.moves[i]);
    }

    // A tenth of the limit is left unused, so that the reply is still on
    // time when the machine is busy and this process is not run for a
    // moment. When alternatives are wanted, the main search leaves them
    // part of the rest.
    long long hardLimit = timeLimitMs > 0 ? max(1LL, timeLimitMs - max(10LL, timeLimitMs / 10)) : -1;
    long long mainLimit = hardLimit;
    if (hardLimit > 0 && alternatives > 0 && rootMoves.size() > 1)
        mainLimit = hardLimit * MAIN_SHARE_WITH_ALTS / 100;
    deadlineMs = mainLimit;

    int best = rootMoves[0];
    int bestScore = 0;
    int depthReached = 0;
    bool completedAll = true;
    vector<int> none;
    long long iterationStart = 0;

    for (int d = 1; d <= maxDepth; d++) {
        int move = 0;
        int score;
        iterationStart = elapsedMs();
        if (d >= ASPIRATION_MIN_DEPTH) {
            int window = ASPIRATION_WINDOW;
            int alpha = max(-INF, bestScore - window), beta = min(INF, bestScore + window);
            while (true) {
                score = searchRoot(d, alpha, beta, rootMoves, none, move);
                if (searchAborted) break;
                if (score <= alpha) alpha = max(-INF, alpha - window);
                else if (score >= beta) beta = min(INF, beta + window);
                else break;
                window *= 2;
                if (window > ASPIRATION_LIMIT) { alpha = -INF; beta = INF; }
            }
        } else {
            score = searchRoot(d, -INF, INF, rootMoves, none, move);
        }
        if (searchAborted) {
            completedAll = false;
            break;
        }

        best = move;
        bestScore = score;
        depthReached = d;

        if (rootMoves.size() == 1) break;
        // A forced mate will not get shorter by looking deeper than its length
        if (abs(score) >= MATE_BOUND && MATE - abs(score) <= d) break;
        if (mainLimit > 0 && d < maxDepth) {
            // The next iteration costs at least about twice the last
            // one; do not start it if it cannot finish.
            long long now = elapsedMs();
            if (now + 2 * (now - iterationStart) >= mainLimit) {
                completedAll = false;
                break;
            }
        }
    }

    if (depthReached == 0) {
        // Not even depth 1 was finished (a limit of a few milliseconds):
        // fall back to the first move by capture ordering.
        best = rootMoves[0];
        searchAborted = false;
        deadlineMs = -1;
        makeMove(best);
        bestScore = -quiesce(-INF, INF, 1, inCheckNow());
        unmakeMove();
    }

    // The next best moves, each found by searching the root again without
    // the moves already chosen. They are searched to the depth of the best
    // move so that their scores compare with its score; the table filled by
    // the main search makes that cheap. One the time limit cuts off is left
    // out rather than reported with a shallower score.
    vector<pair<int, int>> alts;
    if (alternatives > 0 && depthReached > 0) {
        searchAborted = false;
        deadlineMs = hardLimit;
        vector<int> excluded(1, best);
        while (static_cast<int>(alts.size()) < alternatives && excluded.size() < rootMoves.size()) {
            int move = 0;
            int score = searchRoot(depthReached, -INF, INF, rootMoves, excluded, move);
            if (searchAborted || move == 0) break;
            alts.push_back({move, score});
            excluded.push_back(move);
        }
        searchAborted = false;
    }

    cout << "BESTMOVE " << rowOf(FROM(best)) << " " << colOf(FROM(best))
         << " " << rowOf(TO(best)) << " " << colOf(TO(best))
         << " EVAL " << reportScore(bestScore, mover);
    if (!alts.empty()) {
        cout << " ALTS";
        for (auto &alt : alts) {
            cout << " " << rowOf(FROM(alt.first)) << " " << colOf(FROM(alt.first))
                 << " " << rowOf(TO(alt.first)) << " " << colOf(TO(alt.first))
                 << " " << reportScore(alt.second, mover);
        }
    }
    cout << " DEPTH " << depthReached
         << " NODES " << nodesSearched
         << " TTHITS " << tthits
         << " TIME " << elapsedMs()
         << " ENGINE cpp"
         << " STATUS " << (completedAll ? "completed" : "timeout")
         << endl;
}

// ============================================================
//  Command handlers
// ============================================================

/** The legal move from one square to another (promoting to promoType), or 0. */
static int findLegalMove(int from, int to, int promoType) {
    MoveList legal;
    generateLegal(legal, PROMO_ALL);
    for (int i = 0; i < legal.count; i++) {
        int m = legal.moves[i];
        if (FROM(m) == from && TO(m) == to && (!PROMO(m) || PROMO(m) == promoType)) return m;
    }
    return 0;
}

static void handleMoves(int row, int col) {
    int from = SQ(row, col);
    MoveList legal;
    generateLegal(legal, PROMO_QUEEN_ONLY);
    // One entry per target square, in board order
    vector<pair<int, int>> targets;
    for (int i = 0; i < legal.count; i++) {
        int m = legal.moves[i];
        if (FROM(m) == from) targets.push_back({TO(m), m});
    }
    sort(targets.begin(), targets.end());
    cout << "MOVES";
    for (auto &t : targets) {
        cout << " " << rowOf(t.first) << " " << colOf(t.first)
             << " " << (isCapture(t.second) ? 1 : 0)
             << " " << (PROMO(t.second) ? 1 : 0);
    }
    cout << endl;
}

static int promoTypeFromChar(char ch) {
    switch (tolower(static_cast<unsigned char>(ch))) {
        case 'r': return ROOK;
        case 'b': return BISHOP;
        case 'n': return KNIGHT;
        default:  return QUEEN;  // default to queen
    }
}

/**
 * Validates a promotion move, applies it on the board, and returns
 * the new 64-char board string so the Python layer stays in sync.
 */
static void handlePromote(int fr, int fc, int tr, int tc, char promoPiece) {
    int from = SQ(fr, fc), to = SQ(tr, tc);
    int piece = board[from];
    if (piece == EMPTY || colorOf(piece) != side || typeOf(piece) != PAWN) {
        cout << "INVALID Not a pawn" << endl;
        return;
    }
    if (tr != (side == WHITE ? 0 : 7)) {
        cout << "INVALID Not a promotion square" << endl;
        return;
    }
    int m = findLegalMove(from, to, promoTypeFromChar(promoPiece));
    if (!m) {
        cout << "INVALID Illegal move" << endl;
        return;
    }
    makeMove(m);
    cout << "PROMOTE " << serializeBoard() << endl;
}

/**
 * STATUS -> CHECK (in check, has legal moves), CHECKMATE, STALEMATE,
 * DRAW (legal moves exist but neither side can ever mate), OK.
 */
static void handleStatus() {
    bool inCheck = inCheckNow();
    if (!hasLegalMove()) {
        cout << (inCheck ? "STATUS CHECKMATE" : "STATUS STALEMATE") << endl;
    } else if (isInsufficientMaterial()) {
        // A dead position is a draw even while the king is in check.
        cout << "STATUS DRAW" << endl;
    } else {
        cout << (inCheck ? "STATUS CHECK" : "STATUS OK") << endl;
    }
}

/**
 * NOTATION handler: Standard Algebraic Notation for a legal move, with
 * disambiguation (Rfe1, N5f3), promotion and the check or mate suffix.
 * Any other move is answered with "?".
 */
static void handleNotation(int fr, int fc, int tr, int tc, char promo) {
    int from = SQ(fr, fc), to = SQ(tr, tc);
    int piece = board[from];
    bool promotes = piece != EMPTY && typeOf(piece) == PAWN && (tr == 0 || tr == 7);
    int m = piece == EMPTY ? 0 : findLegalMove(from, to, promotes ? promoTypeFromChar(promo) : 0);
    if (!m) {
        cout << "NOTATION ?" << endl;
        return;
    }
    int type = typeOf(piece);
    const string files = "abcdefgh";

    string res;
    if (FLAG(m) == FLAG_CASTLE) {
        res = tc == 6 ? "O-O" : "O-O-O";
    } else if (type == PAWN) {
        // A diagonal pawn move is always a capture
        if (fc != tc) {
            res += files[fc];
            res += 'x';
        }
        res += files[tc];
        res += to_string(8 - tr);
        if (PROMO(m)) {
            res += '=';
            res += "PNBRQK"[PROMO(m)];
        }
    } else {
        res += "PNBRQK"[type];

        // Disambiguation: other pieces of the same kind that can legally
        // move to the same square
        MoveList legal;
        generateLegal(legal, PROMO_QUEEN_ONLY);
        bool others = false, sameFile = false, sameRank = false;
        for (int i = 0; i < legal.count; i++) {
            int o = legal.moves[i];
            if (TO(o) != to || FROM(o) == from || board[FROM(o)] != piece) continue;
            others = true;
            if (colOf(FROM(o)) == fc) sameFile = true;
            if (rowOf(FROM(o)) == fr) sameRank = true;
        }
        if (others) {
            if (!sameFile) {
                res += files[fc];
            } else if (!sameRank) {
                res += to_string(8 - fr);
            } else {
                res += files[fc];
                res += to_string(8 - fr);
            }
        }

        if (board[to] != EMPTY) res += 'x';
        res += files[tc];
        res += to_string(8 - tr);
    }

    // Play the move to see whether it gives check or mate
    makeMove(m);
    if (inCheckNow()) res += hasLegalMove() ? "+" : "#";
    unmakeMove();

    cout << "NOTATION " << res << endl;
}

/** Parse a whole token as a decimal integer, as int() does in main.py. */
static bool parseNumber(const string &token, long long &value) {
    if (token.empty()) return false;
    char *end = nullptr;
    errno = 0;
    value = strtoll(token.c_str(), &end, 10);
    return errno == 0 && *end == '\0';
}

/** The value as an int; main.py has no overflow, so out-of-range values saturate. */
static int saturate(long long value) {
    return static_cast<int>(min<long long>(INT_MAX, max<long long>(INT_MIN, value)));
}

/**
 * Read the earlier positions of the game that follow a BESTMOVE command,
 * from args[first] on, and return their hashes. This replaces the loaded
 * position, so the caller loads the current one again afterwards.
 */
static bool loadHistory(const vector<string> &args, size_t first, vector<uint64_t> &hashes) {
    size_t count = args.size() > first ? args.size() - first : 0;
    if (count % 4 || count / 4 > static_cast<size_t>(MAX_GAME)) return false;
    for (size_t i = first; i < args.size(); i += 4) {
        const string &placement = args[i], &turn = args[i + 1], &rights = args[i + 2], &ep = args[i + 3];
        if (turn != "w" && turn != "b") return false;
        clearBoard();
        int r = 0, c = 0;
        for (char ch : placement) {
            if (ch == '/') {
                if (c != 8) return false;
                r++;
                c = 0;
            } else if (ch >= '1' && ch <= '8') {
                c += ch - '0';
            } else {
                int piece = pieceFromChar(ch);
                if (piece <= EMPTY || r > 7 || c > 7) return false;
                addPiece(piece, SQ(r, c));
                c++;
            }
        }
        if (r != 7 || c != 8) return false;
        int epRow = -1, epCol = -1;
        if (ep != "-") {
            size_t comma = ep.find(',');
            long long row = 0, col = 0;
            if (comma == string::npos || !parseNumber(ep.substr(0, comma), row) ||
                !parseNumber(ep.substr(comma + 1), col))
                return false;
            epRow = saturate(row);
            epCol = saturate(col);
        }
        finishSetup(turn == "w" ? WHITE : BLACK, rights, epRow, epCol);
        hashes.push_back(hashKey);
    }
    return true;
}

// Past the fifty-move rule every clock value plays the same; the cap keeps
// the counter from overflowing as the search adds to it.
static const int MAX_CLOCK = 1 << 20;
// A deeper perft takes minutes; a stray request must not stall the engine
static const int MAX_PERFT_DEPTH = 6;

/**
 * Run one command line, split into tokens. Prints exactly one reply line,
 * or nothing and returns false when the line is malformed.
 */
static bool runCommand(const vector<string> &args) {
    const string &command = args[0];
    // Every command starts with <board64> <rights> <colour> and two
    // integers: the en passant target, or the square for ATTACKED.
    long long n1 = 0, n2 = 0;
    if (args.size() < 6 || !parseNumber(args[4], n1) || !parseNumber(args[5], n2)) return false;
    const string &b = args[1], &rights = args[2], &colour = args[3];
    if (colour != "white" && colour != "black") return false;
    int turn = colour == "white" ? WHITE : BLACK;

    // The squares named after those fields, as row and column pairs
    int sq[4] = {0, 0, 0, 0};
    auto readSquares = [&](size_t count) {
        if (args.size() < 6 + count) return false;
        for (size_t i = 0; i < count; i++) {
            long long v = 0;
            if (!parseNumber(args[6 + i], v) || v < 0 || v > 7) return false;
            sq[i] = static_cast<int>(v);
        }
        return true;
    };

    if (command == "ATTACKED") {
        if (n1 < 0 || n1 > 7 || n2 < 0 || n2 > 7 || !loadPosition(b, rights, WHITE, -1, -1)) return false;
        cout << (attacked(SQ(static_cast<int>(n1), static_cast<int>(n2)), turn) ? "YES" : "NO") << endl;
        return true;
    }

    long long depth = 0;
    if (command == "MOVES") {
        if (!readSquares(2)) return false;
    } else if (command == "BESTMOVE" || command == "PERFT") {
        if (args.size() < 7 || !parseNumber(args[6], depth)) return false;
    } else if (command != "STATUS" && command != "EVAL") {
        if (!readSquares(4)) return false;
    }
    if (!loadPosition(b, rights, turn, saturate(n1), saturate(n2))) return false;
    // A missing promotion piece means a queen
    char promo = args.size() > 10 ? args[10][0] : 'q';

    if (command == "MOVES") {
        handleMoves(sq[0], sq[1]);
    } else if (command == "PROMOTE") {
        handlePromote(sq[0], sq[1], sq[2], sq[3], promo);
    } else if (command == "STATUS") {
        handleStatus();
    } else if (command == "NOTATION") {
        handleNotation(sq[0], sq[1], sq[2], sq[3], promo);
    } else if (command == "EVAL") {
        cout << "EVAL " << evaluate() << endl;
    } else if (command == "PERFT") {
        cout << "PERFT " << (depth < 1 ? 1 : perft(static_cast<int>(min<long long>(depth, MAX_PERFT_DEPTH))))
             << endl;
    } else if (command == "BESTMOVE") {
        long long limitMs = -1, clock = 0, alternatives = 0;
        if ((args.size() > 7 && !parseNumber(args[7], limitMs)) ||
            (args.size() > 8 && !parseNumber(args[8], clock)) ||
            (args.size() > 9 && !parseNumber(args[9], alternatives)))
            return false;
        vector<uint64_t> earlier;
        if (!loadHistory(args, 10, earlier)) return false;
        loadPosition(b, rights, turn, saturate(n1), saturate(n2));
        for (uint64_t h : earlier) repStack[repTop++] = h;
        halfmove = static_cast<int>(min<long long>(max(0LL, clock), MAX_CLOCK));
        handleBestMove(saturate(depth), limitMs, saturate(alternatives));
    }
    return true;
}

int main() {
    initTables();
    static const char *const COMMANDS[] = {"MOVES", "ATTACKED", "PROMOTE", "STATUS", "BESTMOVE",
                                           "NOTATION", "EVAL", "PERFT"};
    string line;
    // One command per line and exactly one reply line per command, so the
    // caller can never be left waiting and replies cannot get out of step.
    while (getline(cin, line)) {
        istringstream in(line);
        vector<string> args;
        for (string token; in >> token;) args.push_back(token);
        if (args.empty()) continue;

        bool known = find(begin(COMMANDS), end(COMMANDS), args[0]) != end(COMMANDS);
        if (args[0] == "VERSION") cout << "VERSION " << PROTOCOL_VERSION << endl;
        else if (!known) cout << "ERROR unknown command" << endl;
        else if (!runCommand(args)) cout << "ERROR malformed command" << endl;
    }
    return 0;
}
