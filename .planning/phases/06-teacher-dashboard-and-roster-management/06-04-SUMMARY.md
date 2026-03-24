---
phase: 06-teacher-dashboard-and-roster-management
plan: 04
subsystem: ui
tags: [onboarding, wizard, settings, sync-status, firestore, dashboard, aeries, seating]

# Dependency graph
requires:
  - phase: 06-teacher-dashboard-and-roster-management/06-01
    provides: dashboard shell with tab navigation and settings section placeholder
  - phase: 06-teacher-dashboard-and-roster-management/06-02
    provides: seatingConfig stored in teachers/{uid}/config/main
  - phase: 06-teacher-dashboard-and-roster-management/06-03
    provides: fetchRoster Cloud Function, roster management UI, preferredName editing

provides:
  - Onboarding wizard (3-step: credentials confirmed -> roster setup -> seating config)
  - checkNeedsOnboarding() reading onboardingComplete flag from teachers/{uid}/config/main
  - completeOnboardingWizard() saving seatingConfig + onboardingComplete:true to Firestore
  - Sync status card on Attendance tab (onSnapshot on teachers/{uid}/sync/status)
  - Full Settings section (credential update, PIN change, account info, sign out)
  - initSettingsUI() called on dashboard open to populate live account data
  - watchSyncStatus() listener started from onTeacherAuthenticated()

affects:
  - 07-PLAN (cloud sync — sync/status doc will be written by Railway sync; this UI reads it)
  - Any future teacher-facing features (onboarding flow is now the entry point for new users)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Onboarding wizard: full-screen overlay z-50 div, showWizardStep(n) shows/hides wizard-step-{n}, progress bar and dots update together"
    - "checkNeedsOnboarding(): reads config/main; returns true if onboardingComplete missing AND no kioskPin/seatingConfig (existing users bypass)"
    - "Sync status card: tiny 2px colored dot + text; red dot + details button on failure; onSnapshot on sync/status doc"
    - "Settings forms: show/hide pattern with Cancel button; success auto-hides after 2s"

key-files:
  created: []
  modified:
    - public/index.html
    - attendance v 2.5.html

key-decisions:
  - "checkNeedsOnboarding detects existing users by presence of kioskPin/seatingConfig/avoidPairs/frontRow — no explicit migration needed for Jeremy"
  - "Wizard step 2 skip is allowed (roster can be set up from the Roster tab later) — wizard step 2 Next only enabled after roster is loaded"
  - "After wizard completion: routes to PIN setup if no PIN, otherwise directly to dashboard (per CONTEXT decision)"
  - "Update Password form calls authenticateTeacher Cloud Function directly — validates new credentials with Aeries immediately"
  - "Sync status card is subtle by design (small dot + text, not a big banner) — per CONTEXT 'not dominant'"

patterns-established:
  - "showOnboardingWizard(username): entry point; hides all other screens; called from handleLogin after checkNeedsOnboarding"
  - "initSettingsUI(): idempotent settings init; safe to call on every showDashboard()"
  - "watchSyncStatus(): started from onTeacherAuthenticated; unsubscribed in handleTeacherLogout alongside other listeners"

# Metrics
duration: 6min
completed: 2026-03-24
---

# Phase 6 Plan 04: Onboarding Wizard and Settings Summary

**3-step onboarding wizard for first-time teachers (credentials -> roster -> seating), sync status card on Attendance tab, and full Settings section with credential update and PIN management**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-24T06:23:15Z
- **Completed:** 2026-03-24T06:29:13Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Built full-screen 3-step onboarding wizard with progress bar and step dots: Step 1 (credentials confirmed), Step 2 (roster fetch/upload with preferred names review), Step 3 (seating mode selection with quick config)
- Added `checkNeedsOnboarding()` that reads `teachers/{uid}/config/main` — returns false for existing users who have kioskPin/seatingConfig so Jeremy is not re-onboarded
- Wizard calls `fetchRoster` Cloud Function (Step 2), reuses `parseRoster()` for CSV upload, and shows editable preferred names list before proceeding
- `completeOnboardingWizard()` saves seatingConfig + `onboardingComplete: true` to Firestore, then routes to PIN setup (if no PIN) or dashboard
- Added sync status card at top of Attendance section: small colored dot + text reading from `teachers/{uid}/sync/status` onSnapshot; shows "Sync not configured yet" when doc absent, green on success, red on failure with expandable error details
- Replaced placeholder Settings section with four cards: Aeries Credentials (username, validated badge, update password form calling `authenticateTeacher`), Kiosk PIN (change form saving to Firestore + kiosk binding), Account Info (username, UID, created/last-login from Firebase Auth metadata), Danger Zone (sign out)
- `initSettingsUI()` called on every `showDashboard()` call to populate live account data

## Task Commits

1. **Task 1: Build onboarding wizard** - `315b1cd` (feat)
2. **Task 2: Add sync status card and Settings section** - `c66eac8` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `public/index.html` - Onboarding wizard HTML+JS, sync status card, full Settings section, watchSyncStatus(), initSettingsUI(), checkNeedsOnboarding(), showOnboardingWizard(), initWizardListeners(), completeOnboardingWizard()
- `attendance v 2.5.html` - Synced to match public/index.html

## Decisions Made

- `checkNeedsOnboarding()` considers a teacher "existing" if their `config/main` doc has `kioskPin`, `seatingConfig`, `avoidPairs`, or `frontRow` fields — this covers Jeremy and anyone who was using the app before this wizard was added, without needing a migration step
- Wizard step 2 has a "Skip for now" button; the Next button is only enabled after a roster is actually loaded — forces teachers to make a conscious choice to skip rather than accidentally skipping
- Update Password form calls `authenticateTeacher` Cloud Function with the new password — this validates the credentials against Aeries immediately rather than just storing them blind
- Sync status card uses a 2px dot indicator (subtle) rather than a full banner — per CONTEXT "visible but not dominant"
- After wizard completion, teacher goes to PIN setup if no PIN set, or directly to dashboard (not kiosk) — per CONTEXT decision confirmed in 06-CONTEXT.md

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external services or environment variables needed. The `sync/status` Firestore doc will be written by the Railway sync in Phase 7; until then the card shows "Sync not configured yet."

## Next Phase Readiness

- Phase 6 complete: all 4 plans done
- New teacher self-service onboarding is fully functional
- Sync status infrastructure (UI side) is ready; Phase 7 just needs to write to `teachers/{uid}/sync/status`
- Settings section provides credential update and PIN change without developer involvement
- Ready for Phase 7: Cloud Sync Worker

---
*Phase: 06-teacher-dashboard-and-roster-management*
*Completed: 2026-03-24*
