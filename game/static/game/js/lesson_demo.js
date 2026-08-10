document.addEventListener(
    "DOMContentLoaded",
    () => {

        const data =
            document.getElementById(
                "board-examples-data"
            );

        if (!data) {
            return;
        }
        let examples = [];

        try {
            examples = JSON.parse(data.textContent);
        } catch (error) {
            console.error("Failed to load lesson examples:", error);
            return;
        }
        let current = 0;

        const pieces = {
            P: "♙",
            N: "♘",
            B: "♗",
            R: "♖",
            Q: "♕",
            K: "♔"
        };

        function renderExample() {

            const example =
                examples[current];

            document.getElementById(
                "example-title"
            ).innerText =
                example.title;

            const board =
                document.getElementById(
                    "demo-board"
                );

            board.innerHTML = "";

            const files =
                ["a","b","c","d","e","f","g","h"];

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
                        "demo-square"
                    );

                    square.classList.add(
                        (
                            row + col
                        ) % 2 === 0
                        ? "demo-light"
                        : "demo-dark"
                    );

                    const squareName =
                        files[col] + row;

                    if (
                        example.highlight.includes(
                            squareName
                        )
                    ) {
                        square.classList.add(
                            "highlight-square"
                        );
                    }

                    if (
                        example.position[
                            squareName
                        ]
                    ) {

                        square.innerHTML =
                            pieces[
                                example.position[
                                    squareName
                                ]
                            ];
                    }

                    board.appendChild(
                        square
                    );
                }
            }
        }

        renderExample();

        document
            .getElementById(
                "next-example-btn"
            )
            .addEventListener(
                "click",
                () => {

                    current++;

                    if (
                        current >=
                        examples.length
                    ) {
                        current = 0;
                    }

                    renderExample();
                }
            );
    }
);