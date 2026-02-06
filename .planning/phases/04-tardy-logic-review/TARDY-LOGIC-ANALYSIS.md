# Tardy Logic Analysis

## Current Logic

The `statusForNow()` function (lines 1252-1283 of `attendance v 2.2.html`) determines whether a student is marked "On Time" or "Late" when they sign in.

### Algorithm

1. Get all sign-in logs for current period, sorted by timestamp
2. If fewer than 5 students have signed in: return "On Time" for everyone
3. Get the 5th student's sign-in timestamp (index 4 in 0-indexed array)
4. Calculate `lateThreshold = 5th student timestamp + 8 minutes`
5. If current time > lateThreshold: return "Late"
6. Otherwise: return "On Time"

### Code Reference

```javascript
function statusForNow(pendingEntry = null) {
  // Get logs for the current period, sorted by timestamp
  // Include any pending entry that hasn't been persisted yet to avoid race conditions
  let allLogs = [...periodAttendanceLog];

  // Add pending entry if provided (for counting purposes during new sign-in)
  if (pendingEntry && !allLogs.some(l => l.StudentID === pendingEntry.StudentID)) {
    allLogs.push(pendingEntry);
  }

  const logs = allLogs
    .map(l => ({ ...l, _ts: getTimestampMs(l) }))
    .filter(l => l._ts !== null)
    .sort((a, b) => a._ts - b._ts);

  // If fewer than 5 students have signed in, everyone is On Time
  if (logs.length < 5) {
    return 'On Time';
  }

  // Get the 5th student's sign-in time (0-indexed, so index 4)
  const fifthStudentTs = logs[4]._ts;
  const lateThreshold = fifthStudentTs + (8 * 60 * 1000); // 8 minutes in ms

  const now = Date.now();

  if (now > lateThreshold) {
    return 'Late';
  }

  return 'On Time';
}
```

### Where Used

| Function | File | Line | Purpose |
|----------|------|------|---------|
| `handleSignIn()` | attendance v 2.2.html | 1396 | Called when student signs in via kiosk |
| `manualCheckIn()` | attendance v 2.2.html | 1628 | Called when admin manually checks in a student |

The status is stored in Firebase and later synced to Aeries via the sync script.

---

## Edge Cases

| # | Case | Current Behavior | Issue |
|---|------|------------------|-------|
| 1 | Fewer than 5 students in period | All marked "On Time" regardless of when they arrive | Small classes (e.g., 4 students) never have tardies even if everyone arrives 30 minutes late |
| 2 | First 5 students arrive late (e.g., all at 8:40 for 8:30 class) | All 5 marked "On Time", threshold set to 8:48 | Actually late students are marked on-time; the threshold is relative to them, not the bell |
| 3 | 5th student is very early (e.g., 8:20 for 8:30 class) | Threshold = 8:28, students arriving at 8:29 marked "Late" | On-time students (before the bell) are incorrectly marked late |
| 4 | Student signs in during passing period | Uses previous period's context if period not switched yet | Status could be calculated against wrong period's data |
| 5 | No bell schedule reference | Logic completely ignores actual class start time | Threshold is entirely relative to peer arrival, not to any absolute time |
| 6 | 5th student arrives at end of class | Threshold could be set to next period's time | Any stragglers would be "On Time" relative to that late threshold |
| 7 | High absenteeism day (only 4 students show up) | All marked "On Time" regardless of arrival time | No tardies recorded even if all 4 students arrive 45 minutes late |

---

## Bell Schedule Configuration

### Location

The `bellSchedules` object is defined in `attendance v 2.2.html` (lines 616-624).

### Structure

```javascript
const bellSchedules = {
  Regular: { 0: "07:28", 1: "08:30", 2: "09:32", 3: "10:52", 4: "11:54", 5: "13:31", 6: "14:33" },
  "Late Start": { 0: "08:37", 1: "09:30", 2: "10:23", 3: "11:28", 4: "12:21", 5: "13:49", 6: "14:42", 7: "15:45" },
  "Assembly Schedule": { 0: "07:37", 1: "08:30", "2A": "09:23", "2B": "10:20", 3: "11:27", 4: "12:20", 5: "13:52", 6: "14:45" },
  "Back to School Night": { 0: "07:28", 1: "08:30", 2: "09:12", 3: "09:54", 4: "10:36", 5: "11:18", 6: "12:00" },
  Finals: { 0: "07:28", 2: "08:30", 4: "10:50", 6: "13:30" },
  "Min Day": { 0: "07:28", 1: "08:30", 2: "09:15", 3: "10:05", 4: "10:50", 5: "11:35", 6: "12:20" },
  Default: { 0: "07:28", 1: "08:30", 2: "09:32", 3: "10:52", 4: "11:54", 5: "13:31", 6: "14:33" }
};
```

### Schedule Types

| Schedule | Description | Periods |
|----------|-------------|---------|
| Regular | Standard school day | 0-6 |
| Late Start | Late start Wednesday | 0-7 |
| Assembly Schedule | Assembly days with 2A/2B | 0-6 (with 2A, 2B) |
| Back to School Night | Shortened periods | 0-6 |
| Finals | Finals schedule (even periods only) | 0, 2, 4, 6 |
| Min Day | Minimum day | 0-6 |
| Default | Fallback (same as Regular) | 0-6 |

### Configuring Bell Times

1. **To change a bell time:** Edit the corresponding value in the `bellSchedules` object
   - Example: Change Period 1 start from "08:30" to "08:35"
   - Modify: `Regular: { 0: "07:28", 1: "08:35", ... }`

2. **To add a new schedule type:** Add a new key-value pair to `bellSchedules`
   - Example: Add a "Rally Schedule"
   - Add: `"Rally Schedule": { 0: "07:28", 1: "08:30", ... }`

3. **To link a date to a schedule:** Edit the `calendarData` object (lines 574-614)
   - Example: `"2026-03-15": "Rally Schedule"`

**Note:** Period start times ARE available in the system via `bellSchedules` but are NOT currently used in tardy calculation. The new logic will use these existing bell times.

---

## Dispute Analysis

Based on PROJECT.md context:

- **15 of 29 corrections (52%) are tardy disputes**
- Students disputing tardies signed in at 8:27-8:34 AM for 8:30 AM class
- These times would be 3 minutes early to 4 minutes late by bell schedule
- But current logic doesn't check bell schedule at all

### Why Disputes Occur

| Student Sign-in | Bell Time | Actual Status | Current Logic Result | Dispute? |
|-----------------|-----------|---------------|---------------------|----------|
| 8:27 AM | 8:30 AM | On Time (3 min early) | Depends on 5th student | Possible |
| 8:31 AM | 8:30 AM | Late (1 min late) | On Time (if 5th arrived late) | No |
| 8:34 AM | 8:30 AM | Late (4 min late) | On Time or Late (random) | Possible |

The unpredictability is the root cause of disputes. Students cannot know their status ahead of time because it depends on when other students arrive.

---

## Root Cause

The current logic creates disputes because:

1. **It's relative (to 5th student) not absolute (to bell time)**
   - A student's status depends on when 5 other students decided to arrive
   - This is fundamentally unpredictable and feels arbitrary to students

2. **A slow 5th student makes everyone after them "late"**
   - If the 5th student arrives at 8:25 for an 8:30 class
   - The threshold becomes 8:33
   - A student arriving at 8:34 is marked "Late" even though they're only 4 minutes late

3. **A fast 5th student makes actual late students appear "on time"**
   - If first 5 students arrive by 8:20 for an 8:30 class
   - Threshold becomes 8:28
   - But the late students that arrive at 8:40 (10 min late) could still be "On Time" if enough others arrived before them

4. **The 8-minute buffer is arbitrary and doesn't match school policy**
   - There's no documentation for why 8 minutes was chosen
   - It doesn't align with any stated school policy
   - Teachers cannot explain to students why they're late

5. **Small classes are exempt**
   - Classes with fewer than 5 students never get tardies
   - This creates inconsistency across the school

---

## Recommendation

### Proposed New Logic

Replace the relative 5th-student logic with absolute bell-schedule-based logic:

```javascript
// Configuration constant (adjust based on school policy)
const TARDY_GRACE_MINUTES = 5;

function statusForNow() {
  const p = periodSelect.value;
  if (!p) return 'On Time'; // No period selected

  const sched = bellSchedules[scheduleName] || bellSchedules.Default;
  const periodStartTime = sched[p];
  if (!periodStartTime) return 'On Time'; // No bell time defined

  // Parse period start time to today's date
  const [hours, minutes] = periodStartTime.split(':').map(Number);
  const periodStart = new Date();
  periodStart.setHours(hours, minutes, 0, 0);

  // Calculate tardy threshold
  const tardyThreshold = periodStart.getTime() + (TARDY_GRACE_MINUTES * 60 * 1000);

  const now = Date.now();

  if (now <= tardyThreshold) {
    return 'On Time';
  }
  return 'Late';
}
```

### Configuration Points

1. **Bell times:** Edit `bellSchedules` object to adjust period start times
2. **Grace period:** Change `TARDY_GRACE_MINUTES` constant to adjust tolerance
3. **Per-schedule grace:** Could extend to have different grace periods per schedule type

### Benefits

| Benefit | Description |
|---------|-------------|
| Deterministic | Same time = same status, always |
| Matches school policy | Based on actual bell times |
| No edge cases | Works regardless of class size or peer arrival times |
| Transparent | Students can calculate their own status |
| Configurable | Grace period adjustable to match school policy |
| Already supported | Bell times already exist in `bellSchedules` |

### Migration Considerations

1. **Announce the change** to students and staff before implementing
2. **Choose appropriate grace period** based on school policy (recommend 3-5 minutes)
3. **Test thoroughly** on a single period before full rollout
4. **Monitor dispute rate** after implementation to verify improvement

---

## Code Verification

| Function | File | Lines | Verified |
|----------|------|-------|----------|
| statusForNow() | attendance v 2.2.html | 1252-1283 | [x] Confirmed |
| bellSchedules | attendance v 2.2.html | 616-624 | [x] Confirmed |
| calendarData | attendance v 2.2.html | 574-614 | [x] Confirmed |
| handleSignIn() calls statusForNow | attendance v 2.2.html | 1396 | [x] Confirmed |
| manualCheckIn() calls statusForNow | attendance v 2.2.html | 1628 | [x] Confirmed |
| getTimestampMs() helper | attendance v 2.2.html | 1239-1249 | [x] Confirmed |

### Verification Notes

- Line 1396: `const status = statusForNow(pendingEntry);` inside `handleSignIn()`
- Line 1628: `const status = statusForNow();` inside `manualCheckIn()`
- Both functions use the same logic, but `handleSignIn()` passes a `pendingEntry` to avoid race conditions
- The `bellSchedules` object is already used extensively for period detection and display, just not for tardy logic
