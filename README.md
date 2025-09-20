# Attendance & Group Assigner

This project provides a single-page kiosk and admin dashboard for tracking classroom attendance, exporting logs, and assigning students to collaborative groups. The app is designed to run entirely from `index.html`, using Tailwind CSS for styling and Firebase Firestore for real-time storage and synchronization across kiosks.

## Features

- **Teacher admin panel** with auto-detected or manual period selection, roster management, attendance summaries, and CSV exports.
- **Kiosk mode** for students to sign in with their ID, view their status, and receive a randomly balanced group assignment that respects seating constraints.
- **Exceptions management** including front-row assignments and avoid-pair rules that synchronize across kiosks.
- **Schedule tools** to upload bell schedules and calendars, and to export full attendance history for a date range including absences.
- **Offline support** that caches rosters and sign-ins locally when Firebase is unavailable.

## Getting Started

1. Open `index.html` in a modern browser. The page includes all styling and scripts required to run the kiosk.
2. Configure your Firebase project credentials by updating the `window.__firebase_config` object near the top of the file.
3. (Optional) Set a consistent `window.__app_id` value for all kiosks you deploy so that they share data within the same Firestore namespace.
4. Upload class rosters and (optionally) schedules from the admin panel to begin tracking attendance.

## Development Notes

- The application relies on the Firebase web SDK v10 (modular) for auth and Firestore access.
- Tailwind CSS is loaded from a CDN; no additional build steps are required.
- All business logic, UI updates, and automated tests are contained within `index.html` for ease of deployment.

