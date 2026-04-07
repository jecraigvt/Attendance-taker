# Codebase Review Status

This document coordinates a comprehensive 7-topic codebase review. It is designed to be picked up by multiple AI agents in parallel. 

**Instructions for Agents:**
1. Pick an unassigned "Session" from the list below.
2. Update the document to state: `Status: IN PROGRESS by Agent [X]`.
3. Conduct the review corresponding to your topic and section.
4. When finished, change the status to `Status: DONE`, and add a brief summary of findings or actions taken under the **Notes** section.

---

## 1. Frontend State & The useEffect Trap
*Focus: Memory leaks, missing cleanup functions (event listeners, WebSockets, Firestore onSnapshot), stale closures, and redundant state.*

- [x] **Session 1.1**: Review `Section 1: Authentication & User Profile Components`
  - Status: DONE
  - Notes:
    **Scope note:** This is a kiosk + Python sync app (no React, no user profiles). Auth review covers: HTML kiosk admin access, Firebase anonymous auth, and Python service-account auth.

    **Findings:**

    1. **[MEDIUM] TEACHER_CODE is client-side only** (`attendance v 2.2.html:562`)
       - `const TEACHER_CODE = "****"` is embedded in the `<script>` block. Any student with DevTools open on the tablet can read it and access the admin panel.
       - Admin panel toggle is pure CSS (`classList.add/remove('hidden')`) — no server-side enforcement.
       - **Recommendation:** Consider obfuscating the check with a salted hash, or accept the risk since kiosk tablets should be in restricted access mode (Guest OS account, F11 kiosk mode, etc.).

    2. **[LOW] No admin session timeout** (`attendance v 2.2.html:793`)
       - Once the teacher enters the code and opens the admin panel, it stays open indefinitely — no idle timeout or re-lock.
       - **Recommendation:** Add a `setTimeout` (e.g., 5 min of no interaction) that hides admin and returns to kiosk mode.

    3. **[INFO] Firebase anonymous auth — correct pattern for kiosk**
       - `signInAnonymously(auth)` at line 821 is the right choice for a public kiosk. No credentials required of students.
       - Security model relies entirely on **Firebase Security Rules** (not visible in this repo). If rules are misconfigured, any anonymous user with the projectId could read/write attendance data.
       - **Recommendation:** Verify Firebase Security Rules are scoped to `artifacts/attendance-taker-56916/public/**` and restrict writes to authenticated-but-anonymous tokens if not already done.

    4. **[INFO] Firebase web config hardcoded in HTML** (`attendance v 2.2.html:44-52`)
       - `apiKey`, `projectId`, etc. are embedded. This is standard/required Firebase practice for web apps — the API key is not a secret. Security is enforced by Firebase Rules, not key secrecy. No action needed.

    5. **[GOOD] Firestore `onSnapshot` listeners are properly unsubscribed before re-subscription**
       - `unsubRosters()` called at line 867 before re-attaching.
       - `unsubExceptions()` called at line 1010 before re-attaching.
       - `unsubAttendance()` called at line 1068 before re-attaching.
       - No listener leak found for the page's lifecycle (kiosk never navigates away so `beforeunload` cleanup is not critical).

    6. **[INFO] Python side auth is clean**
       - Service account key loaded via `FIREBASE_KEY_PATH` env var (`attendance_to_aeries.py:15`).
       - Lazy init via `get_db()` prevents import-time failures.
       - `attendance-key.json` is correctly untracked in git.
       - Aeries credentials (`AERIES_USER`, `AERIES_PASS`) from Windows env vars — no hardcoded secrets in Python files.
- [ ] **Session 1.2**: Review `Section 2: Dashboard & Class Roster Views`
  - Status: PENDING
  - Notes: 
- [ ] **Session 1.3**: Review `Section 3: Grading, Assignment & Rubric Editor Components`
  - Status: PENDING
  - Notes: 
- [ ] **Session 1.4**: Review `Section 4: Global Context & Custom Hooks`
  - Status: PENDING
  - Notes: 

## 2. Data Lifecycle & Orphaned Data (Cascading Deletes)
*Focus: Orphaned Firebase subcollections after parent deletion, Soft vs. Hard deletes, and TTL (Time-To-Live) cleanup for temp data.*

- [ ] **Session 2.1**: Review `Section 1: Users, Classes & Rosters Data Models`
  - Status: PENDING
  - Notes: 
- [ ] **Session 2.2**: Review `Section 2: Assignments, Submissions & Grading Data Models`
  - Status: PENDING
  - Notes: 
- [ ] **Session 2.3**: Review `Section 3: Background Jobs / Cloud Functions (Data Cleanup)`
  - Status: PENDING
  - Notes: 

## 3. UI/UX "Happy Path" Bias (Weird Viewports & Long Text)
*Focus: Text overflow/truncation, empty states for new users, layout shifts (CLS) on fetch, and responsive flexbox behaviors.*

- [ ] **Session 3.1**: Review `Section 1: Core Layouts, Navbars & Mobile Viewports`
  - Status: PENDING
  - Notes: 
- [ ] **Session 3.2**: Review `Section 2: Empty States (Onboarding, No Classes, No Data)`
  - Status: PENDING
  - Notes: 
- [ ] **Session 3.3**: Review `Section 3: Lists, Tables & Cards (Testing long names/titles)`
  - Status: PENDING
  - Notes: 

## 4. Accessibility (a11y) & Semantic HTML
*Focus: `div`-soup onClick handlers (missing keyboard support), focus trapping inside modals, and ARIA labels for icon-only buttons.*

- [ ] **Session 4.1**: Review `Section 1: Buttons, Forms & Inputs`
  - Status: PENDING
  - Notes: 
- [ ] **Session 4.2**: Review `Section 2: Modals, Dialogs & Dropdowns (Focus management)`
  - Status: PENDING
  - Notes: 
- [ ] **Session 4.3**: Review `Section 3: General Navigation & Page Structure`
  - Status: PENDING
  - Notes: 

## 5. Environment & Deployment Boundaries
*Focus: Secret leakage (React/Vite env vars), CORS strictness, and Staging vs. Prod data separation.*

- [ ] **Session 5.1**: Review `Section 1: Environment Variables & Secrets (.env files, Config)`
  - Status: PENDING
  - Notes: 
- [ ] **Session 5.2**: Review `Section 2: API Routes & Cors Configurations`
  - Status: PENDING
  - Notes: 
- [ ] **Session 5.3**: Review `Section 3: Third-Party Integrations (Stripe, Email, LLM API keys)`
  - Status: PENDING
  - Notes: 

## 6. Observability & Proactive Monitoring
*Focus: Contextual logging (errors with userId/classId), and unhandled promise rejections / 3rd-party API failures.*

- [ ] **Session 6.1**: Review `Section 1: Frontend Error Boundaries & Global Catch-alls`
  - Status: PENDING
  - Notes: 
- [ ] **Session 6.2**: Review `Section 2: API/Backend Error Logging & Formatting`
  - Status: PENDING
  - Notes: 
- [ ] **Session 6.3**: Review `Section 3: Async Task Handling (PDF extraction, LLM generation queues)`
  - Status: PENDING
  - Notes: 

## 7. Dependency Bloat & Client Performance
*Focus: Unnecessary heavy imports (e.g. moment.js, lodash), lack of lazy loading for large components (PDF viewers, rich text).*

- [ ] **Session 7.1**: Review `Section 1: package.json Audit & Import Analysis`
  - Status: PENDING
  - Notes: 
- [ ] **Session 7.2**: Review `Section 2: Component Lazy Loading Strategies (React.lazy)`
  - Status: PENDING
  - Notes: 
- [ ] **Session 7.3**: Review `Section 3: Data Fetching Optimization (React Query setup, deduplication)`
  - Status: PENDING
  - Notes: 
