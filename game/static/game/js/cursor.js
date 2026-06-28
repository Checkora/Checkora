
let cursor = document.querySelector(".cursor");

if (!cursor) {
    cursor = document.createElement("div");
    cursor.className = "cursor";
    document.body.appendChild(cursor);
}
    const cursorDropdown = document.querySelector('.cursor-dropdown');
    const cursorTrigger = document.getElementById('cursorTypeTrigger');
    const cursorTypeLabel = document.getElementById('cursorTypeLabel');
    const cursorOptions = document.querySelectorAll('.cursor-type-option');
    let activeCursor = 'default';

    if (activeCursor === 'default') {
        cursor.style.display = 'none';
    } else {
        cursor.style.display = 'block';
    }
    let mouseX = 0;
    let mouseY = 0;

    document.addEventListener('mousemove', e => {
      mouseX = e.clientX;
      mouseY = e.clientY;
    });

    function updateCursorPosition() {
      cursor.style.left = `${mouseX}px`;
      cursor.style.top = `${mouseY}px`;
      requestAnimationFrame(updateCursorPosition);
    }

    updateCursorPosition();
    const allowedCursorTypes = [
        "default",
        "glow",
        "trail",
        "sparkle",
        "orbit",
    ];

    function updateCursorType(type) {
      activeCursor = type;
      cursor.className = 'cursor';
      
      if (type !== 'default') {
          cursor.classList.add(type);
          cursor.style.opacity = '0.98';
          cursor.style.display = 'block';
      } else {
          cursor.style.opacity = '0';
          cursor.style.display = 'none';
      }
      if (cursorTypeLabel) {
    cursorTypeLabel.textContent =
        type.charAt(0).toUpperCase() + type.slice(1);
}

cursorOptions.forEach(option => {
    option.classList.toggle(
        'selected',
        option.dataset.cursor === type
    );
});
      try {
    window.localStorage.setItem("cursorType", type);
} catch (error) {
    // Ignore storage access errors.
}
    }

    

let savedCursor = "default";

    try {
        const storedCursor = window.localStorage.getItem("cursorType");
        if (allowedCursorTypes.includes(storedCursor)) {
            savedCursor = storedCursor;
        }
    } 
    catch (error) {
        // Ignore storage access errors.
    }

updateCursorType(savedCursor);
    
    if (cursorDropdown && cursorTrigger && cursorTypeLabel) {

    cursorTrigger.addEventListener('click', e => {
    e.stopPropagation();

    document.querySelectorAll('.profile-dropdown.active').forEach(menu => {
        menu.classList.remove('active');
    });

    cursorDropdown.classList.toggle('active');

    const expanded = cursorDropdown.classList.contains('active');
    cursorTrigger.setAttribute('aria-expanded', expanded);
});

    cursorOptions.forEach(option => {
        option.addEventListener('click', () => {
            updateCursorType(option.dataset.cursor);
            cursorDropdown.classList.remove('active');
            cursorTrigger.setAttribute('aria-expanded', 'false');
        });
    });

    document.addEventListener('click', e => {
        if (!cursorDropdown.contains(e.target)) {
            cursorDropdown.classList.remove('active');
            cursorTrigger.setAttribute('aria-expanded', 'false');
        }
    });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            cursorDropdown.classList.remove('active');
            cursorTrigger.setAttribute('aria-expanded', 'false');
        }
    });
}
    document.addEventListener('click', function(e) {
        document.querySelectorAll('.profile-dropdown.active').forEach(function(menu) {
            if (!menu.contains(e.target)) {
                menu.classList.remove('active');
            }
        });
    });
  