let lessonSteps = [];
let currentStep = 0;
let initialPosition = {};
let currentLegalMoves = [];

function getKnightMoves(square) {

    const file =
        square.charCodeAt(0);

    const rank =
        parseInt(square[1]);

    const offsets = [
        [-2,-1],
        [-2,1],
        [-1,-2],
        [-1,2],
        [1,-2],
        [1,2],
        [2,-1],
        [2,1]
    ];

    const moves = [];

    offsets.forEach(
        ([df,dr]) => {

            const newFile =
                file + df;

            const newRank =
                rank + dr;

            if (
                newFile >= 97 &&
                newFile <= 104 &&
                newRank >= 1 &&
                newRank <= 8
            ) {

                moves.push(
                    String.fromCharCode(
                        newFile
                    ) + newRank
                );
            }
        }
    );

    return moves;
}

function getPawnMoves(square) {

    const file =
        square[0];

    const rank =
        parseInt(square[1]);

    const moves = [];

    if (rank < 8) {

        moves.push(
            file + (rank + 1)
        );
    }

    return moves;
}

function getKingMoves(square) {

    const file =
        square.charCodeAt(0);

    const rank =
        parseInt(square[1]);

    const moves = [];

    for (
        let df = -1;
        df <= 1;
        df++
    ) {

        for (
            let dr = -1;
            dr <= 1;
            dr++
        ) {

            if (
                df === 0 &&
                dr === 0
            ) {
                continue;
            }

            const newFile =
                file + df;

            const newRank =
                rank + dr;

            if (
                newFile >= 97 &&
                newFile <= 104 &&
                newRank >= 1 &&
                newRank <= 8
            ) {

                moves.push(
                    String.fromCharCode(
                        newFile
                    ) + newRank
                );
            }
        }
    }

    return moves;
}

function getRookMoves(square) {

    const file =
        square[0];

    const rank =
        parseInt(square[1]);

    const moves = [];

    for (
        let r = 1;
        r <= 8;
        r++
    ) {

        if (r !== rank) {

            moves.push(
                file + r
            );
        }
    }

    const files =
        ["a","b","c","d","e","f","g","h"];

    files.forEach(
        f => {

            if (f !== file) {

                moves.push(
                    f + rank
                );
            }
        }
    );

    return moves;
}

function getBishopMoves(square) {

    const moves = [];

    const file =
        square.charCodeAt(0);

    const rank =
        parseInt(square[1]);

    [
        [1,1],
        [1,-1],
        [-1,1],
        [-1,-1]
    ].forEach(
        ([df,dr]) => {

            let f =
                file + df;

            let r =
                rank + dr;

            while (
                f >= 97 &&
                f <= 104 &&
                r >= 1 &&
                r <= 8
            ) {

                moves.push(
                    String.fromCharCode(
                        f
                    ) + r
                );

                f += df;
                r += dr;
            }
        }
    );

    return moves;
}

function getQueenMoves(square) {

    return [
        ...getRookMoves(
            square
        ),
        ...getBishopMoves(
            square
        )
    ];
}

document.addEventListener(
    "DOMContentLoaded",
    () => {

        const positionData =
            document.getElementById(
                "practice-position-data"
            );

        if (!positionData) {
            return;
        }

        const position =
            JSON.parse(
                positionData.textContent
            );
        
        initialPosition =
            JSON.parse(
                JSON.stringify(position)
            )
        
        const lessonStepsData =
            document.getElementById(
                "lesson-steps-data"
            );

        lessonSteps =
            JSON.parse(
                lessonStepsData.textContent
            );

        currentStep = 0;

        document.getElementById(
            "lesson-instruction"
        ).textContent =
            lessonSteps[0].instruction;

        const board =
            document.getElementById(
                "practice-board"
            );

        const files =
            ["a", "b", "c", "d", "e", "f", "g", "h"];

        const pieces = {
            P: "♙",
            N: "♘",
            B: "♗",
            R: "♖",
            Q: "♕",
            K: "♔"
        };

        board.innerHTML = "";

        for (
            let row = 8;
            row >= 1;
            row--
        ) {

            for (
                let col = 0;
                col < 8;
                col++
            ) {

                const square =
                    document.createElement(
                        "div"
                    );

                square.classList.add(
                    "lesson-square"
                );

                square.classList.add(
                    (
                        row + col
                    ) % 2 === 0
                        ? "light"
                        : "dark"
                );

                const squareName =
                    files[col] + row;

                square.dataset.square =
                    squareName;

                if (
                    position[squareName]
                ) {

                    square.innerHTML =
                        pieces[
                        position[
                        squareName
                        ]
                        ];
                }

                board.appendChild(
                    square
                );
            }
        }

        let selectedSquare = null;

        board.addEventListener(
            "click",
            (event) => {

                const square =
                    event.target.closest(
                        ".lesson-square"
                    );

                if (!square) {
                    return;
                }

                if (!selectedSquare) {
                    const piece = square.innerHTML.trim();
                    if (!piece) {
                        return;
                    }

                    selectedSquare = square;

                    square.classList.add(
                        "selected-square"
                    );

                    let moves = [];

                    if (piece === "♘") {

                        moves =
                            getKnightMoves(
                                square.dataset.square
                            );
                    }

                    if (piece === "♙") {

                        moves =
                            getPawnMoves(
                                square.dataset.square
                            );
                    }

                    if (piece === "♔") {

                        moves =
                            getKingMoves(
                                square.dataset.square
                            );
                    }

                    if (piece === "♖") {

                        moves =
                            getRookMoves(
                                square.dataset.square
                            );
                    }

                    if (piece === "♗") {

                        moves =
                            getBishopMoves(
                                square.dataset.square
                            );
                    }

                    if (piece === "♕") {

                        moves =
                            getQueenMoves(
                                square.dataset.square
                            );
                    }

                    currentLegalMoves = moves;

                    moves.forEach(
                        move => {

                            const target =
                                board.querySelector(
                                    `[data-square="${move}"]`
                                );

                            if (target) {

                                target.classList.add(
                                    "valid-move"
                                );
                            }
                        }
                    );

                    return;
                }

                const from =
                    selectedSquare.dataset.square;

                const to =
                    square.dataset.square;

                const move =
                    from + "-" + to;
                if (
                    !currentLegalMoves.includes(
                        to
                    )
                ) {

                    return;
                }
                
                const sourceSquare =
                    selectedSquare;
                
                selectedSquare.classList.remove(
                    "selected-square"
                );

                document
                    .querySelectorAll(
                        ".valid-move"
                    )
                    .forEach(
                        square => {
                            square.classList.remove(
                                "valid-move"
                            );
                        }
                    );

                selectedSquare = null;

                const isCorrect = checkMove(move);
                if (isCorrect) {

                const piece =
                    sourceSquare.innerHTML;

                square.innerHTML =
                    piece;

                sourceSquare.innerHTML =
                    "";
                }
            }
        );

        const retryBtn = document.getElementById("retry-btn");
        if (retryBtn) {
            retryBtn.addEventListener("click", () => {
                location.reload();
            });
        }
    }
);

function checkMove(move) {

    if (
        currentStep >=
        lessonSteps.length
    ) {
        return false;
    }

    const expectedMove =
        lessonSteps[
            currentStep
        ].expected_move;

    const result =
        document.getElementById(
            "lesson-result"
        );

    if (
        move === expectedMove
    ) {

        result.textContent =
            "✅ Correct Move!";

        result.style.color =
            "#4caf50";

        currentStep++;

        if (currentStep < lessonSteps.length) {

            document.getElementById(
                "lesson-instruction"
            ).textContent =
                lessonSteps[
                    currentStep
                ].instruction;

        } else {

            document.getElementById(
                "lesson-instruction"
            ).textContent =
                "🎉 Lesson Complete!";

            result.textContent =
                "🏆 Great Job!";

            result.style.color =
                "#4caf50";
        }

        return true;

    } else {

        result.textContent =
            "❌ Try Again";

        result.style.color =
            "#ff5252";
        document.getElementById(
            "retry-btn"
        ).style.display =
            "inline-block";

        return false;
    }
}