# Tardy Logic Change Validation

## Configuration

- TARDY_GRACE_MINUTES: 5
- Schedule: Regular
- Period 1 start time: 08:30

## Test Scenarios

| # | Scenario | Sign-in Time | Old Logic Result | New Logic Result | Expected | Pass? |
|---|----------|--------------|------------------|------------------|----------|-------|
| 1 | First student, on time | 08:28 | On Time | On Time | On Time | Yes |
| 2 | Student 2 min after bell | 08:32 | On Time (if <5 students) | On Time | On Time | Yes |
| 3 | Student at grace boundary | 08:35 | On Time (if <5 students) | On Time | On Time | Yes |
| 4 | Student 1 min after grace | 08:36 | On Time (if <5 students) | Late | Late | Yes |
| 5 | Student 10 min late | 08:40 | Varies by 5th student | Late | Late | Yes |
| 6 | Small class (3 students), last one 10 min late | 08:40 | On Time (always) | Late | Late | Yes |
| 7 | Passing period sign-in | 09:25 (P2 at 09:32) | Varies | On Time | On Time | Yes |
| 8 | Late Start schedule, P1 at 09:30 | 09:33 | Varies | On Time | On Time | Yes |

## Edge Cases from Original Analysis

| Edge Case | Old Behavior | New Behavior | Improvement |
|-----------|--------------|--------------|-------------|
| <5 students in period | All "On Time" regardless of actual arrival | Uses bell time + grace period | Small classes now have appropriate tardies |
| First 5 students arrive late | All marked "On Time", creates wrong threshold | Uses bell time + grace period | Actually late students marked late |
| 5th student very early | Wrong threshold established, on-time students marked late | Uses bell time + grace period | On-time students stay on-time |
| No bell schedule reference | Ignored actual class start time | Uses actual bell schedule times | Matches school policy exactly |
| 5th student arrives end of class | Created impossibly late threshold | Uses bell time + grace period | Threshold is always reasonable |
| High absenteeism day | No tardies possible if <5 students show | Uses bell time regardless of attendance count | Tardy logic works even with low attendance |

## Projected Dispute Impact

Based on PROJECT.md data:
- 15 of 29 corrections (52%) were tardy disputes
- Students disputed tardies signed in 8:27-8:34 AM for 8:30 class
- Root cause: Unpredictable threshold based on 5th student arrival

### With New Logic (5-minute grace = 08:35 threshold for 8:30 class):

| Sign-in Time | Old Logic | New Logic | Dispute Likely? |
|--------------|-----------|-----------|-----------------|
| 8:27 | Varies | On Time | No |
| 8:28 | Varies | On Time | No |
| 8:29 | Varies | On Time | No |
| 8:30 | Varies | On Time | No |
| 8:31 | Varies | On Time | No |
| 8:32 | Varies | On Time | No |
| 8:33 | Varies | On Time | No |
| 8:34 | Varies | On Time | No |
| 8:35 | Varies | On Time | No |
| 8:36+ | Varies | Late | Unlikely (clearly late) |

**Analysis:**
- Most disputed tardies (8:27-8:34) would now correctly show "On Time"
- Students arriving 8:36+ are clearly past the grace period (6+ minutes late)
- Threshold is deterministic - students can predict their status

**Projected Results:**
- **Estimated tardy dispute reduction:** 10-12 of 15 tardy disputes eliminated (67-80% reduction)
- **Overall correction reduction:** From 29 total to ~17-19 (35-40% reduction)
- **Remaining corrections:** Primarily sync failures (17%) and no-sign-in cases (31%)

## Recommendations

### Immediate (This Week)

1. **Monitor first week of operation**
   - Track total tardy count vs historical average
   - Watch for unexpected edge cases
   - Document any new disputes

2. **Verify bell schedule accuracy**
   - Confirm bellSchedules object matches actual school times
   - Test with different schedule types (Late Start, Assembly, etc.)

### Short-term (First Month)

3. **Adjust grace period if needed**
   - TARDY_GRACE_MINUTES can be changed from 5 to any value
   - If too many disputes: increase grace period
   - If too lenient: decrease grace period

4. **Document policy for stakeholders**
   - Make grace period visible to students/parents
   - Clear communication prevents disputes

### Future Enhancements

5. **Consider per-period grace periods**
   - Some periods might need different thresholds
   - Example: Period 1 might need longer grace for traffic delays

6. **Admin UI for configuration**
   - Allow adjusting TARDY_GRACE_MINUTES without code changes
   - Per-schedule or per-period overrides

---

*Validation document created: 2026-02-05*
*Implementation reference: 04-02-SUMMARY.md*
