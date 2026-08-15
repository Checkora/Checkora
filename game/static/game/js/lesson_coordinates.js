
    document.addEventListener("DOMContentLoaded", () => {
        const toggle = document.getElementById('lessonCoordToggle');
        if (!toggle) return;
    
        // 1. Read preference from localStorage (Default is true)
        const storedValue = localStorage.getItem('showLessonCoordinates');
        const showCoords = storedValue !== 'false'; 
        
        // Set initial UI state
        toggle.checked = showCoords;
        applyCoordinateVisibility(showCoords);
    
        // 2. Listen for clicks on the checkbox
        toggle.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            localStorage.setItem('showLessonCoordinates', isChecked);
            applyCoordinateVisibility(isChecked);
        });
    
        // 3. Function to show/hide coordinates on all boards safely
        function applyCoordinateVisibility(show) {
            const wrappers = document.querySelectorAll('.lesson-board-aligned');
            wrappers.forEach(wrapper => {
                if (show) {
                    wrapper.classList.remove('hide-coordinates');
                } else {
                    wrapper.classList.add('hide-coordinates');
                }
            });
        }
    });
  
