#include <iostream>
#include <string>
#include <cmath>
#include <cctype>

using namespace std;

class Board {
public:
    char squares[64];

    Board() {
        string startPos = 
            "rnbqkbnr"
            "pppppppp"
            "........"
            "........"
            "........"
            "........"
            "PPPPPPPP"
            "RNBQKBNR";
        
        for (int i = 0; i < 64; i++) {
            squares[i] = startPos[i];
        }
    }

    int toIndex(string square) {
        int col = square[0] - 'a';
        int row = 8 - (square[1] - '0');
        return row * 8 + col;
    }

    int getRow(int index) { return index / 8; }
    int getCol(int index) { return index % 8; }

    bool isPawnMoveValid(int fromIdx, int toIdx, char piece) {
        int fromRow = getRow(fromIdx);
        int fromCol = getCol(fromIdx);
        int toRow = getRow(toIdx);
        int toCol = getCol(toIdx);

        int direction = (piece == 'P') ? -1 : 1; 
        int startRow = (piece == 'P') ? 6 : 1;   

        if (fromCol == toCol) {
            if (toRow == fromRow + direction) {
                return squares[toIdx] == '.'; 
            }
            if (toRow == fromRow + 2 * direction && fromRow == startRow) {
                int midIdx = (fromIdx + toIdx) / 2; 
                return squares[toIdx] == '.' && squares[midIdx] == '.';
            }
        }
        
        if (abs(fromCol - toCol) == 1 && toRow == fromRow + direction) {
            if (squares[toIdx] != '.') return true;
        }

        return false;
    }

    bool isKnightMoveValid(int fromIdx, int toIdx) {
        int dRow = abs(getRow(fromIdx) - getRow(toIdx));
        int dCol = abs(getCol(fromIdx) - getCol(toIdx));
        return (dRow * dRow + dCol * dCol) == 5;
    }

    bool isMoveValid(string move) {
        int fromIdx = toIndex(move.substr(0, 2));
        int toIdx = toIndex(move.substr(2, 2));
        char piece = squares[fromIdx];

        if (piece == '.') return false;

        char type = tolower(piece);
        
        if (type == 'p') {
            return isPawnMoveValid(fromIdx, toIdx, piece);
        }
        else if (type == 'n') {
            return isKnightMoveValid(fromIdx, toIdx);
        }

        return true; 
    }

    void makeMove(string move) {
        int fromIdx = toIndex(move.substr(0, 2));
        int toIdx = toIndex(move.substr(2, 2));
        squares[toIdx] = squares[fromIdx];
        squares[fromIdx] = '.';
    }

    void printBoard() {
        cerr << "   a b c d e f g h" << endl;
        for (int i = 0; i < 8; i++) {
            cerr << (8 - i) << "  "; 
            for (int j = 0; j < 8; j++) {
                cerr << squares[i * 8 + j] << " ";
            }
            cerr << endl;
        }
    }
};

int main() {
    Board board;
    string move;

    if (cin >> move) {
        if (board.isMoveValid(move)) {
            board.makeMove(move);
            // board.printBoard(); // Optional: Uncomment for debugging
            cout << "VALID " << move << endl;
        } else {
            cout << "INVALID " << move << endl;
        }
    }
    return 0;
}