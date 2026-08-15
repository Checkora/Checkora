document.addEventListener("DOMContentLoaded", () => {

    const board =
        document.getElementById("board");

    if (!board) {
        return;
    }

    const pieces = {
        P: "♙",
        N: "♘",
        B: "♗",
        R: "♖",
        Q: "♕",
        K: "♔"
    };

    const lessonPosition = [
        ["", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["", "", "", "", "P", "", "", ""],
        ["", "", "", "", "", "B", "N", ""]
    ];

    let selectedSquare = null;

    buildBoard();

    function buildBoard() {

        board.innerHTML = "";

        const files =
            ["a", "b", "c", "d", "e", "f", "g", "h"];

        lessonPosition.forEach((row, r) => {

            row.forEach((piece, c) => {

                const square =
                    document.createElement("div");

                square.classList.add(
                    "lesson-square"
                );

                square.classList.add(
                    (r + c) % 2 === 0
                        ? "light"
                        : "dark"
                );

                const squareName =
                    files[c] + (8 - r);

                square.dataset.square =
                    squareName;

                square.innerHTML =
                    pieces[piece] || "";

                square.addEventListener(
                    "click",
                    () => handleSquareClick(square)
                );

                board.appendChild(square);
            });
        });
    }

    function handleSquareClick(square) {

        if (!selectedSquare) {

            if (
                square.innerHTML === ""
            ) {
                return;
            }

            selectedSquare = square;

            square.style.outline =
                "3px solid red";

            return;
        }

        const from =
            selectedSquare.dataset.square;

        const to =
            square.dataset.square;

        selectedSquare.style.outline =
            "";

        movePiece(from, to);

        selectedSquare = null;
    }

    function movePiece(from, to) {

        const fromSquare =
            document.querySelector(
                `[data-square="${from}"]`
            );

        const toSquare =
            document.querySelector(
                `[data-square="${to}"]`
            );

        if (
            !fromSquare ||
            !toSquare
        ) {
            return;
        }

        const piece =
            fromSquare.innerHTML;

        if (!piece) {
            return;
        }

        toSquare.innerHTML =
            piece;

        fromSquare.innerHTML =
            "";

        if (
            window.checkLessonMove
        ) {

            window.checkLessonMove(
                from + "-" + to
            );
        }
    }
});