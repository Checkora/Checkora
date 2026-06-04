document.addEventListener("DOMContentLoaded", () => {

    const lessonDataElement =
        document.getElementById("lesson-steps");

    if (!lessonDataElement) {
        return;
    }

    const lessonSteps =
        JSON.parse(lessonDataElement.textContent);

    let currentStep = 0;

    function loadStep() {

        if (
            currentStep >= lessonSteps.length
        ) {
            return;
        }

        const step =
            lessonSteps[currentStep];

        const instruction =
            document.getElementById(
                "lesson-instruction"
            );

        if (instruction) {

            instruction.innerHTML =
                step.instruction;
        }

        console.log(
            "Current Lesson Step:",
            step
        );
    }

    function completeLesson() {

        const result =
            document.getElementById(
                "lesson-result"
            );

        if (result) {

            result.innerHTML =
                "🏆 Lesson Completed!";

            result.style.color =
                "#4caf50";
        }
    }

    function nextStep() {

        currentStep++;

        if (currentStep < lessonSteps.length) {

            loadStep();

        } else {

            completeLesson();
        }
    }

    window.checkLessonMove = function (moveNotation) {

        if (currentStep >= lessonSteps.length) {
            return;
        }

        const step = lessonSteps[currentStep];
        const result =
            document.getElementById(
                "lesson-result"
            );
        
        if (moveNotation === step.expected_move) {
            if (result) {

                result.innerHTML =
                    "✅ Correct Move!";

                result.style.color =
                    "#4caf50";
            }

            setTimeout(() => {

                nextStep();

            }, 1000);

        } else {
            if (result) {
                result.innerHTML =
                    "❌ Try again";

                result.style.color =
                    "#f44336";
            }
        }
    };
    
    loadStep();
});