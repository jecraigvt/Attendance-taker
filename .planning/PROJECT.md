# Attendance Sync Reliability

## What This Is

A school attendance system that captures student sign-ins via tablet kiosks, stores them in Firebase, and syncs to Aeries (the official student information system). Currently experiencing ~2-3% error rate (3-5 students/day out of 150) due to sync failures and tardy logic issues. This project makes the sync reliable and reviews the tardy calculation.

## Core Value

Every student who signs in must have their correct attendance status reflected in Aeries. A single sync failure should never result in a student being incorrectly marked absent.

## Requirements

### Validated

- ✓ Student sign-in via tablet kiosk — existing
- ✓ Firebase storage of attendance records — existing
- ✓ Basic sync to Aeries via Playwright automation — existing
- ✓ Scheduled sync 7x daily (once per period + end of day) — existing

### Active

- [ ] Retry logic with exponential backoff when sync fails
- [ ] More frequent sync schedule (every 15-20 min instead of once per period)
- [ ] Audit logging of what was sent to Aeries vs what Firebase shows
- [ ] Review and fix tardy calculation logic (8-min threshold after 5th student)
- [ ] Post-sync verification report (compare Firebase to sync attempt)
- [ ] Graceful handling of Aeries UI selector changes

### Out of Scope

- Sign-in app changes — students forgetting to sign in is a user behavior issue, not a system bug
- Aeries API integration — would require district IT approval; stick with UI automation for now
- Real-time sync — batch sync is sufficient given school schedule
- Mobile app — tablet kiosks are working fine

## Context

**Current flow:**
```
Student → Tablet kiosk → Firebase → Sync script → Aeries
```

**Known issues from analysis:**
- 2/4 Period 6: 5 students signed in "On Time" but marked absent in Aeries (sync failure)
- 9 of 29 corrections: students never signed in (not a system bug)
- 15 of 29 corrections: students dispute their "Late" status (tardy logic question)

**Tardy logic (current):**
- First 5 students are always "On Time"
- After 5th student, anyone signing in 8+ minutes later is "Late"
- Students disputing tardies signed in at 8:27-8:34 AM for a class that may start at 8:30 AM

**Technical environment:**
- Python 3.x with firebase-admin, Playwright
- Firebase Firestore for data storage
- Windows Task Scheduler for automated runs
- Aeries SIS accessed via browser automation (no API)

## Constraints

- **Aeries access**: Push-only via browser automation; cannot query attendance data back
- **Selector brittleness**: Aeries UI changes break automation; need defensive selectors
- **Timing**: Syncs must complete within period transitions (~7 min passing time)
- **Credentials**: Stored in Windows environment variables

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep browser automation | Aeries API not available without district IT approval | — Pending |
| Focus on sync reliability | 17% of errors are sync failures; 31% are user error (no sign-in) | — Pending |
| Review tardy logic | 52% of complaints are tardy disputes | — Pending |

---
*Last updated: 2026-02-04 after initialization*
