# Requirements: Attendance Taker v2.0

**Defined:** 2026-03-23
**Core Value:** Every student who signs in must have their correct attendance status reflected in Aeries. The system must work reliably for multiple teachers without requiring technical support.

## v2.0 Requirements

### Authentication & Data Isolation

- [ ] **AUTH-01**: Teacher can sign in with their Aeries username/password
- [ ] **AUTH-02**: Teacher can easily update their Aeries password when it changes
- [ ] **AUTH-03**: Aeries credentials are encrypted at rest (Fernet encryption, key in Railway env)
- [ ] **AUTH-04**: Each teacher's rosters and attendance data are isolated under their UID in Firestore
- [ ] **AUTH-05**: Firestore security rules prevent teachers from accessing each other's data
- [ ] **AUTH-06**: Jeremy's existing data is migrated to the new per-teacher structure without data loss

### Teacher Dashboard

- [ ] **DASH-01**: Teacher sees sync status (last sync time, success/failure, error details)
- [ ] **DASH-02**: Teacher onboarding flow guides first-time setup (enter Aeries creds, configure seating)
- [ ] **DASH-03**: Teacher can update Aeries credentials through the web UI at any time

### Roster Management

- [ ] **ROST-01**: Playwright auto-fetches class rosters from Aeries using teacher's credentials
- [ ] **ROST-02**: Rosters refresh automatically on a schedule (e.g., weekly or on-demand)

### Seating Configuration

- [ ] **SEAT-01**: Teacher can configure group-based seating (group names, sizes, front-row groups)
- [ ] **SEAT-02**: Teacher can configure individual desk-based seating (desk names/numbers)
- [ ] **SEAT-03**: Teacher can choose between group or individual desk mode during setup
- [ ] **SEAT-04**: Teacher can turn off seat assignment entirely

### Kiosk Integration

- [ ] **KIOSK-01**: Kiosk tablet links to a specific teacher after teacher logs in once
- [ ] **KIOSK-02**: Student sign-ins write to the correct teacher's data path

### Cloud Sync

- [ ] **SYNC-01**: Aeries attendance sync runs on Railway (Docker + Playwright), not local PC
- [ ] **SYNC-02**: Each teacher's attendance syncs every 20 minutes during school hours
- [ ] **SYNC-03**: Teacher is notified on dashboard when sync fails

### Self-Healing Automation

- [ ] **HEAL-01**: When Aeries UI changes break selectors, Gemini Flash identifies replacement selectors
- [ ] **HEAL-02**: If Flash fails to repair, escalate to Gemini Pro
- [ ] **HEAL-03**: Selectors stored in a config file (not hardcoded), so LLM patches are trackable and git-versioned

## Future Requirements

- Multi-school support (different Aeries instances)
- Student-facing features (sign-in kiosk UI redesign)
- Email/SMS notifications for sync failures
- Analytics dashboard (attendance trends across teachers)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Aeries API integration | Requires district IT approval; stick with browser automation |
| Mobile app | Tablet kiosks and web app are sufficient |
| Real-time sync | 20-min batch sync is sufficient given school schedule |
| Student account management | Students just enter IDs, no accounts needed |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | TBD | Pending |
| AUTH-02 | TBD | Pending |
| AUTH-03 | TBD | Pending |
| AUTH-04 | TBD | Pending |
| AUTH-05 | TBD | Pending |
| AUTH-06 | TBD | Pending |
| DASH-01 | TBD | Pending |
| DASH-02 | TBD | Pending |
| DASH-03 | TBD | Pending |
| ROST-01 | TBD | Pending |
| ROST-02 | TBD | Pending |
| SEAT-01 | TBD | Pending |
| SEAT-02 | TBD | Pending |
| SEAT-03 | TBD | Pending |
| SEAT-04 | TBD | Pending |
| KIOSK-01 | TBD | Pending |
| KIOSK-02 | TBD | Pending |
| SYNC-01 | TBD | Pending |
| SYNC-02 | TBD | Pending |
| SYNC-03 | TBD | Pending |
| HEAL-01 | TBD | Pending |
| HEAL-02 | TBD | Pending |
| HEAL-03 | TBD | Pending |

**Coverage:**
- v2.0 requirements: 23 total
- Mapped to phases: 0
- Unmapped: 23

---
*Requirements defined: 2026-03-23*
