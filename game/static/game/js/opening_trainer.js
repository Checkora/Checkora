const movesElement =
    document.getElementById("opening-moves");

if (!movesElement) {
    throw new Error(
        "opening-moves element not found"
    );
}

const OPENING_MOVES = JSON.parse(
    movesElement.textContent
);

let currentMove = 0;

const feedback =
    document.getElementById("trainer-feedback");

const progress =
    document.getElementById("move-progress");

const moveInput =
    document.getElementById("move-input");

const checkButton =
    document.getElementById("check-move-btn");


function updateProgress() {
    progress.innerText =
        `${currentMove} / ${OPENING_MOVES.length}`;
}


function completeOpening() {
    feedback.innerText =
        "🎉 Opening completed successfully!";

    moveInput.disabled = true;
    checkButton.disabled = true;
}


function validateMove(move) {
    const expectedMove =
        OPENING_MOVES[currentMove];

    if (move.toLowerCase() === expectedMove.toLowerCase()) {

        currentMove++;

        feedback.innerText =
            "✅ Correct move!";

        updateProgress();

        moveInput.value = "";

        if (
            currentMove >=
            OPENING_MOVES.length
        ) {
            completeOpening();
        }

        return true;
    }

    feedback.innerText =
        `❌ Incorrect move. Expected: ${expectedMove}`;

    return false;
}


checkButton.addEventListener(
    "click",
    () => {

        const move =
            moveInput.value.trim();

        if (!move) {
            feedback.innerText =
                "Please enter a move.";

            return;
        }

        validateMove(move);
    }
);


moveInput.addEventListener(
    "keypress",
    (event) => {

        if (event.key === "Enter") {
            checkButton.click();
        }
    }
);


updateProgress();