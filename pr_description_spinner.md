# Feature: Add Loading Spinner on Login & Register Buttons

## Description
This PR improves the user experience during authentication by providing immediate visual feedback when the "Sign In" or "Create Account" buttons are clicked. It prevents double submissions and ensures users are aware that their request is being processed.

## Changes Made
- **CSS Spinner Animation**: Added a lightweight, CSS-only spinner in `auth.css`.
- **Button Loading State**: Implemented a `.loading` class for buttons that hides the text and centers the spinner.
- **JavaScript Integration**:
  - Automatically injects the spinner into the submit button upon form submission.
  - Disables pointer events on the button to prevent multiple clicks.
  - Implemented a `pageshow` listener to reset the button state if the user navigates back to the page (fixing the "stuck spinner" issue).
- **Global Auth Support**: The logic in `auth.js` automatically applies to all forms on the login and registration pages.

## Testing Done
- Verified that the spinner appears immediately upon clicking "Sign In".
- Verified that the button is disabled while the spinner is active.
- Verified that using the browser "Back" button resets the button to its original state.
- Verified that the layout remains consistent across mobile and desktop viewports.

Fixes #452
