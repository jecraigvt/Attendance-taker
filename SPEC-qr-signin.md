# QR Code Sign-In — Technical Specification

## Overview

Students scan a QR code displayed on the classroom kiosk with their personal phone to sign in to attendance. The QR code rotates every 2 minutes to prevent link sharing. After the first sign-in, the student's phone remembers them so future sign-ins are instant (scan = signed in). The system tracks devices to detect and flag when one phone signs in multiple students.

---

## User Flows

### Flow 1: First-Time Student Sign-In
1. Teacher's kiosk displays a QR code in the corner of the screen
2. Student scans QR with their phone camera
3. Phone opens a lightweight web page: `https://attendance-taker-56916.web.app/s?t=TEACHER_UID&c=Xk9mQ2`
4. Page shows a simple ID input field: "Enter your student ID"
5. Student types their 5-digit ID and taps "Sign In"
6. Cloud Function validates the QR code, finds the student on the roster, runs seating algorithm
7. Phone shows: "Welcome, Madison! Group 7 — Seat 2"
8. Student ID is saved in phone's localStorage for future auto-sign-in
9. A random device ID is also generated and stored in localStorage

### Flow 2: Returning Student Sign-In (Daily Use)
1. Student scans QR code
2. Page loads, detects stored student ID in localStorage
3. Automatically submits sign-in (no typing required)
4. Phone shows: "Welcome, Madison! Group 7 — Seat 2"
5. Total time: ~2 seconds from scan to confirmation

### Flow 3: Same-Device Multi-Sign-In (Flagged)
1. Madison signs in on her phone (normal flow)
2. Madison's friend Derek asks to use her phone to sign in
3. Derek scans QR on Madison's phone
4. Page shows warning: "This device is registered to Madison Anderson. Sign in as a different student?"
5. If Derek proceeds and types his ID, the sign-in goes through BUT:
   - The attendance record is tagged with `deviceAlert: true`
   - A device alert is written to Firestore
   - Teacher's dashboard shows: "Madison Anderson and Derek Sawada signed in from the same device"

### Flow 4: Expired/Invalid QR Code
1. Student scans an old QR code (screenshot from yesterday, shared link, etc.)
2. Cloud Function rejects it: code doesn't match or is expired
3. Phone shows: "This code has expired. Scan the QR code on the screen."

### Flow 5: Student Not on Roster
1. Student scans QR and enters an ID not on any roster
2. Cloud Function rejects it
3. Phone shows: "Student ID not found. Please check your ID and try again."

---

## Architecture

### Components

```
┌─────────────────┐         ┌──────────────────┐        ┌──────────────┐
│  Kiosk Screen   │         │  Student's Phone  │        │  Cloud Func  │
│  (existing app) │         │  (/s page)        │        │  (qrSignIn)  │
├─────────────────┤         ├──────────────────┤        ├──────────────┤
│ Generates QR    │         │ Reads URL params  │        │ Validates    │
│ code every 2min │         │ (teacher, code)   │───────>│ QR code      │
│ Stores session  │         │                   │        │ Finds student│
│ in Firestore    │         │ Sends sign-in     │        │ Runs seating │
│                 │         │ request to CF     │<───────│ Writes to    │
│ Displays QR in  │         │                   │        │ Firestore    │
│ corner of kiosk │         │ Shows result:     │        │ Returns name │
│                 │         │ name, group, seat │        │ + group/seat │
└─────────────────┘         └──────────────────┘        └──────────────┘
```

### QR Code Generation (Kiosk Side)

**When:** Every 2 minutes while kiosk is active, and on period change.

**Kiosk ID:** Each kiosk generates a random ID on first load and stores it in localStorage (`kioskInstanceId`). This identifies which kiosk wrote which QR session, so multiple kiosks don't overwrite each other.

**Logic:**
```
1. On kiosk load: read or generate kioskInstanceId from localStorage
2. Generate random 8-character alphanumeric code
3. Write to Firestore: teachers/{uid}/config/qrSessions/{kioskInstanceId}
   {
     code: "Xk9mQ2pR",
     period: "3",
     createdAt: serverTimestamp()   // CF computes expiry: reject if serverNow - createdAt > 150 seconds (2min + 30s grace)
   }
4. Encode URL as QR: https://attendance-taker-56916.web.app/s?t={uid}&c={code}
5. Display QR on kiosk screen
6. Repeat every 2 minutes
```

**QR Display:**
- Small QR code (~120px) in the bottom-right corner of the kiosk screen
- Subtle label underneath: "Scan to sign in"
- QR visually refreshes every 2 minutes (brief fade transition)
- Does not interfere with normal kiosk ID input

### Mobile Sign-In Page (/s)

**URL:** `https://attendance-taker-56916.web.app/s?t=TEACHER_UID&c=CODE`

**Page Structure:**
- Standalone HTML page (not the main app)
- Minimal: no navigation, no sidebar, just sign-in
- Mobile-optimized, large touch targets
- No Firebase Auth required (anonymous access)

**Page Logic:**
```
1. Parse URL params: teacherUid (t), code (c)
2. Check localStorage for stored student ID and device ID
3. If no device ID exists, generate one (random UUID) and store it
4. If stored student ID exists:
   a. Show "Signing in as [stored name]..."
   b. Auto-submit to Cloud Function
   c. On success: show welcome + seat assignment
   d. On failure: clear stored ID, show manual input
5. If no stored student ID:
   a. Show ID input field + "Sign In" button
   b. On submit: call Cloud Function
   c. On success: store student ID + name in localStorage, show welcome
   d. On failure: show error message
```

**localStorage Keys (on student's phone):**
```
qr_device_id:   "a7f3b2c1-..." (random UUID, generated once, persists forever)
qr_student_id:  "54321"        (stored after first successful sign-in)
qr_student_name: "Madison Anderson" (for display on auto-sign-in)
```

**Same-Device Warning:**
```
If localStorage has qr_student_id AND the user tries to enter a DIFFERENT ID:
  → Show warning: "This device is registered to Madison Anderson.
     Signing in as a different student will be flagged. Continue?"
  → If they continue: sign-in proceeds with deviceAlert: true
  → If they cancel: return to auto-sign-in flow
```

### Cloud Function: qrSignIn

**Type:** HTTPS Callable (onCall)
**Auth:** None required (anonymous access)
**Region:** us-central1

**Input:**
```json
{
  "teacherUid": "kia7YLhmzqNF...",
  "code": "Xk9mQ2pR",
  "studentId": "54321",
  "deviceId": "a7f3b2c1-...",
  "previousStudentId": "12345" or null  (if device was registered to someone else)
}
```

**Validation Steps:**
```
1. Verify teacherUid exists in Firestore
2. Read ALL docs from teachers/{uid}/config/qrSessions/ (one per kiosk)
3. Find any session where code matches AND serverNow - createdAt <= 150 seconds
   → If none match: return { success: false, error: "expired" }
4. Read current period from the matched session's period field
5. Look up studentId in the roster for that period
   → Also check other periods (smart switch logic)
   → If not found: return { success: false, error: "not_found" }
6. **Use a Firestore Transaction for steps 6-9** to prevent double-writes from concurrent requests (e.g., student mashing Sign In on spotty cellular):
7. Check if student already signed in for this period today
   → If so: return existing record { success: true, recheck: true, name: "Madison", group: 7, seat: 2, status: "On Time" }
8. Determine status (On Time / Late) using same tardy logic as kiosk
9. Run seating algorithm (if enabled) to get group + seat
10. Write attendance record to Firestore:
   teachers/{uid}/attendance/{date}/periods/{period}/students/{studentId}
   {
     StudentID: "54321",
     Name: "Madison Anderson",
     Date: "4/3/2026",
     SignInTime: "8:42:15 AM",
     Status: "On Time",
     Period: "3",
     Group: 7,
     Seat: 2,
     Timestamp: serverTimestamp(),
     signInMethod: "qr",
     deviceId: "a7f3b2c1-..."
   }
10. If previousStudentId is set and differs from studentId:
    Write device alert:
    teachers/{uid}/attendance/{date}/deviceAlerts/{deviceId}
    {
      students: ["Madison Anderson (54321)", "Derek Sawada (54320)"],
      period: "3",
      timestamp: serverTimestamp()
    }
    Also set deviceAlert: true on the attendance record.
11. Return success response:
    {
      success: true,
      name: "Madison Anderson",
      group: 7,
      seat: 2,
      status: "On Time",
      period: "3",
      deviceAlert: false
    }
```

**Error Responses:**
```json
{ "success": false, "error": "expired", "message": "This code has expired. Scan the QR code again." }
{ "success": false, "error": "not_found", "message": "Student ID not found on the roster." }
{ "success": true, "recheck": true, "name": "Madison", "group": 7, "seat": 2, "message": "Already signed in." }
{ "success": false, "error": "invalid_teacher", "message": "Invalid QR code." }
```

### Seating Algorithm in Cloud Function

The kiosk currently runs seating client-side. The Cloud Function needs the same logic. Options:

**Option A: Duplicate the algorithm in the Cloud Function.**
- Pro: Self-contained, no extra round-trips
- Con: Two copies of seating logic to maintain

**Option B: Cloud Function writes a "pending" sign-in, kiosk picks it up via onSnapshot and assigns the seat, then updates Firestore.**
- Pro: Single source of seating logic (client-side)
- Con: Adds latency (student waits for kiosk to process), more complex

**Recommendation: Option A.** The seating algorithm is relatively simple (find least-full group respecting front-row, avoid-pairs, and capacity). Duplicating it in the Cloud Function keeps the QR sign-in fast and self-contained. The kiosk's onSnapshot listener will pick up the new attendance record and update the UI in real time.

### Firestore Structure

**New documents (QR sessions — one per kiosk, written by kiosk, read by Cloud Function):**
```
teachers/{uid}/config/qrSessions/{kioskInstanceId}
{
  code: "Xk9mQ2pR",
  period: "3",
  createdAt: serverTimestamp()
}
```
Multiple kiosks each write their own session doc. The Cloud Function reads all of them and matches against any valid code.

**Modified attendance record (additional fields for QR sign-ins):**
```
teachers/{uid}/attendance/{date}/periods/{period}/students/{studentId}
{
  ...existing fields...,
  signInMethod: "qr",        // "kiosk" for normal sign-ins (optional, backwards-compatible)
  deviceId: "a7f3b2c1-...",  // only for QR sign-ins
  deviceAlert: true/false     // true if same device signed in different student
}
```

**New document (device alerts — for teacher dashboard):**
```
teachers/{uid}/attendance/{date}/deviceAlerts/{deviceId}
{
  students: ["Madison Anderson (54321)", "Derek Sawada (54320)"],
  period: "3",
  timestamp: Timestamp
}
```

### Firestore Security Rules

The mobile page has no Firebase Auth context. The Cloud Function (admin SDK) bypasses security rules. No rule changes needed — the mobile page never touches Firestore directly.

The `qrSessions/{kioskId}` documents are readable by the Cloud Function (admin SDK — already bypasses rules). Each kiosk writes its own session doc (authenticated as the teacher — already has write access to their own docs).

### QR Code Library

Use `qrcode` library via CDN for client-side QR generation on the kiosk:
```html
<script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js"></script>
```

Generate QR as a canvas element displayed on the kiosk screen.

---

## UI Details

### Kiosk Screen (QR Code Display)
```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│                   Welcome Warriors!                      │
│         Enter your 5-digit student ID                    │
│                                                          │
│                    [ _ _ _ _ _ ]                          │
│                    [ Sign In  ]                           │
│                                                          │
│                                              ┌────────┐  │
│                                              │ ██████ │  │
│                                              │ ██  ██ │  │
│                                              │ ██████ │  │
│                                              └────────┘  │
│                                             Scan to sign │
│                                                in        │
└──────────────────────────────────────────────────────────┘
```

### Mobile Sign-In Page (/s)

**First visit (no stored ID):**
```
┌─────────────────────┐
│                     │
│   ✓ Seat Assigner   │
│                     │
│   Enter your        │
│   student ID:       │
│                     │
│   ┌───────────────┐ │
│   │     54321     │ │
│   └───────────────┘ │
│                     │
│   ┌───────────────┐ │
│   │    Sign In    │ │
│   └───────────────┘ │
│                     │
└─────────────────────┘
```

**Returning visit (auto-sign-in):**
```
┌─────────────────────┐
│                     │
│        ✓            │
│                     │
│   Welcome,          │
│   Madison!          │
│                     │
│   Group 7 — Seat 2  │
│   Period 3          │
│                     │
│   Signed in at      │
│   8:42 AM           │
│                     │
│   ┌───────────────┐ │
│   │  Not Madison? │ │
│   └───────────────┘ │
│                     │
└─────────────────────┘
```

**Same-device warning:**
```
┌─────────────────────┐
│                     │
│   ⚠ This device is  │
│   registered to     │
│   Madison Anderson  │
│                     │
│   Signing in as a   │
│   different student │
│   will be flagged.  │
│                     │
│   ┌───────────────┐ │
│   │   Continue    │ │
│   └───────────────┘ │
│   ┌───────────────┐ │
│   │ Sign in as    │ │
│   │   Madison     │ │
│   └───────────────┘ │
│                     │
└─────────────────────┘
```

---

## Settings Toggle

**Location:** Settings tab, new "QR Sign-In" card

**UI:**
```
┌──────────────────────────────────────────────┐
│  QR Code Sign-In                             │
│  Allow students to sign in by scanning a     │
│  QR code with their phone.                   │
│                                              │
│  [  Toggle  ○ ] Enable QR Sign-In            │
└──────────────────────────────────────────────┘
```

**Firestore:**
```
teachers/{uid}/config/main
{
  ...existing fields...,
  qrSignInEnabled: true/false   (default: false)
}
```

**Behavior when disabled (default):**
- No QR code shown on kiosk screen
- QR session not generated (no Firestore writes)
- If a student visits `/s` with a valid teacher UID, Cloud Function returns `{ success: false, error: "qr_disabled" }`
- Mobile page shows: "QR sign-in is not enabled for this class."

**Behavior when enabled:**
- QR code appears in bottom-right of kiosk screen
- Session codes rotate every 2 minutes
- Full QR sign-in flow active

**On toggle change:**
- Toggle on → immediately start generating QR codes, show on kiosk
- Toggle off → hide QR from kiosk, stop generating codes, clear active session from Firestore

---

## Build Order

1. **Cloud Function `qrSignIn`**
   - Validate QR code against Firestore session
   - Look up student on roster (with smart period switching)
   - Determine tardy status
   - Run seating algorithm
   - Write attendance record
   - Handle device alerts
   - Return name, group, seat, status

2. **QR Session Generation (kiosk)**
   - Generate random code every 2 minutes
   - Write to Firestore `config/qrSessions/{kioskInstanceId}`
   - Regenerate on period change
   - Use QR code library to render on kiosk screen

3. **Mobile Sign-In Page (`/s` or `/signin.html`)**
   - Standalone HTML page (minimal, mobile-optimized)
   - Parse URL params (teacher UID, code)
   - localStorage: device ID generation, student ID storage
   - Auto-sign-in flow for returning students
   - Manual ID entry for first-time students
   - Success screen with name, group, seat
   - Error handling (expired, not found, already signed in)

4. **Device Tracking + Warning**
   - Generate and persist device UUID in localStorage
   - Detect same-device different-student scenarios
   - Show warning before proceeding
   - Pass alert flag to Cloud Function

5. **Teacher Dashboard Alerts**
   - Read deviceAlerts collection for today
   - Display in Attendance Insights section
   - Show which students shared a device

6. **QR Code Display on Kiosk**
   - Small QR in bottom-right corner
   - Refreshes every 2 minutes with subtle animation
   - Label: "Scan to sign in"

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Student scans QR but has no internet | Browser shows offline error (not our page) |
| Student scans QR during period transition | Code includes period; if period changed, old code expires, new code issued |
| Student is on roster for multiple periods | Cloud Function checks all periods (smart switch), picks the best match |
| Teacher hasn't selected a period yet | QR session not generated until a period is active |
| Student clears localStorage / uses incognito | Treated as first-time sign-in; no device warning (they lose auto-sign-in convenience too) |
| Two students legitimately share a phone | Warning shown but sign-in proceeds; teacher sees the flag and can verify |
| Kiosk browser tab is closed/refreshed | QR generation restarts on page load; session picks up current period |
| Cloud Function cold start | First QR sign-in of the day may take 2-3 seconds; subsequent ones are fast |
| Student signed in via kiosk, tries QR too | Returns existing record with seat reminder; no duplicate |
| Student mashes Sign In on bad connection | Firestore Transaction ensures only one write; others return existing record |
| Multiple kiosks running for same teacher | Each kiosk writes its own session doc; CF accepts code from any active kiosk |
| Student scans at 1:59 of a 2:00 code | 30-second grace period accepts the code until 2:30 |
| Teacher disables seating | QR sign-in works, just no group/seat in response |
| Non-Aeries account (mwilliams) | QR works the same; seating optional; no sync to Aeries |

---

## Security Summary

| Threat | Mitigation |
|--------|-----------|
| Student saves/shares QR link | Code expires in 2 minutes; useless after that |
| Student guesses a QR code | 8-char alphanumeric = 2.8 trillion combinations |
| Student signs in absent friend | Device fingerprint flags same-device multi-sign-in |
| Student spoofs device ID | Requires clearing localStorage or incognito; loses auto-sign-in convenience |
| Direct API calls to qrSignIn | Still needs valid unexpired code + valid student ID on roster |
| Replay attack (resubmit old request) | Code expired; "already signed in" check |
| Student accesses Firestore directly | Mobile page has no Firebase Auth; only admin SDK (Cloud Functions) can write attendance |
