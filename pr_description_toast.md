# Feature: Replace Default Alerts with Toast Notifications

## Description
This PR replaces standard browser `alert()` calls and static Django error lists with a modern, non-blocking toast notification system. This improves the visual consistency of the application and ensures that user interaction is never interrupted by modal popups.

## Changes Made
- **Centralized Notification Engine**: Created `toast.js` and `toast.css` to provide a reusable `showToast()` function.
- **Global Override**: Overrode `window.alert` to automatically route all JS alerts to the new toast system.
- **Django Integration**: Added auto-detection for Django messages and form validation errors, displaying them as toasts.
- **Visual Polish**: Implemented a "frosted glass" (glassmorphism) design with backdrop-blur and smooth entry/exit animations.
- **Consistency**: Integrated the system across `login`, `register`, `board`, and `landing` pages.
- **Fixes**: Resolved merge conflicts and broken template references in `views.py`.

## Testing Done
- Verified that `window.alert()` triggers a toast notification.
- Verified that incorrect login/registration inputs trigger "error" toasts.
- Verified that successful actions trigger "success" toasts.
- Tested auto-fade and manual dismissal functionality.
- Confirmed responsiveness on mobile and desktop viewports.

Fixes #450
