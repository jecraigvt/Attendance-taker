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
3. Set a consistent `window.__app_id` value for every kiosk that should share data within the same Firestore namespace.
4. Upload class rosters and (optionally) schedules from the admin panel to begin tracking attendance.

## Multi-teacher setup

To let multiple teachers use their own rosters, group configurations, and seating exceptions, give each teacher an isolated Firestore namespace and a unique layout document.

1. **Clone and customize `index.html` for each teacher.** Create a copy of the file (or deploy per-teacher versions) so you can give them individual settings.
2. **Assign a unique `window.__app_id`.** In each teacher's copy, set `window.__app_id` to a unique value (for example, `"ms-salas-periods"`, `"mr-lee-periods"`, etc.). Firestore stores all rosters, seating exceptions, and attendance data under that ID, so distinct values keep their data completely separate.
3. **Give each teacher a `window.__teacher_id`.** Set a distinct value such as their email prefix or initials. Group layout preferences (max group count, seats per group, which groups count as front row, etc.) are stored per teacher ID, so this keeps layout changes from colliding.
4. **Allow their Google account to sign in.** Update the `window.__teacher_allowlist` / `window.__teacher_emails` array (or `window.__teacher_domain`) so their Google login is authorized to open the Teacher Admin panel.
5. **Distribute the personalized link.** Share the customized `index.html` (or its hosted URL) with the teacher. When they sign in with their allowed Google account they can upload their own roster, set seating exceptions, configure group sizes/front-row tags, and manage attendance without affecting anyone else.

> **Note:** If two teachers intentionally need to share the same rosters and exceptions, give them the *same* `window.__app_id` and (optionally) distinct `window.__teacher_id` values. Only the app ID determines who sees which rosters/exceptions; the teacher ID controls layout preferences.

## Development Notes

- The application relies on the Firebase web SDK v10 (modular) for auth and Firestore access.
- Tailwind CSS is loaded from a CDN; no additional build steps are required.
- All business logic, UI updates, and automated tests are contained within `index.html` for ease of deployment.
