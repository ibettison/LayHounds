# Five-Runner Rule Betfair Test Report

Generated: 2026-06-18

## Purpose

Test the proposed rule before applying it to the app:

- accept 5-runner races normally
- do not accept races with fewer than 5 runners
- still reject 5-runner races when there is a strong favourite probability gap
- keep the revised Favourite Risk Guard rules:
  - probability gap greater than 20%
  - Trap 1/2 favourite only blocked below 300m
  - second-favourite fallback blocked when the second favourite is Trap 1 or 2 below 300m

The comparison is against the current revised guard, which skips races with 5 or fewer runners.

## Data Loaded

| Metric | Result |
| --- | ---: |
| Archive | `C:\Users\nib8\Downloads\data.tar` |
| Countries tested | UK/IE Betfair markets |
| Archive members scanned | 156,891 |
| Market files scanned | 151,275 |
| WIN markets found | 43,830 |
| UK/IE settled snapshots used | 20,806 |
| Non-UK/IE markets skipped | 22,493 |

## Test Setup

- Stake: `0.05`
- Favourites configured: `2`
- Commission: market base rate from Betfair, falling back to `5%`
- Max recovery level: `3`
- Max liability cap: `5.00`
- Settlement: actual race winner from Betfair historical data
- Odds: actual BSP odds from Betfair historical data

## P/L Comparison

| Metric | Current: skip 5 or fewer | Proposed: accept 5, skip fewer than 5 unless strong gap | Difference |
| --- | ---: | ---: | ---: |
| Total guard P/L | GBP 12.40 | GBP -133.37 | GBP -145.76 |
| Maximum drawdown | GBP 55.79 | GBP 200.21 | GBP +144.43 |
| Busts | 114 | 222 | +108 |
| Total guard bets | 18,679 | 30,846 | +12,167 |
| First-favourite bets | 7,998 | 13,872 | +5,874 |
| Second-favourite bets | 10,681 | 16,974 | +6,293 |
| Fallback second-favourite bets | 2,683 | 3,102 | +419 |
| No-bet skips | 10,125 | 3,832 | -6,293 |
| Fallback P/L | GBP -32.23 | GBP -59.53 | GBP -27.30 |
| Average liability | GBP 0.4358 | GBP 0.3957 | GBP -0.0401 |
| Worst losing run | 3 | 4 | +1 |

## First-Favourite Guard Comparison

| Metric | Current: skip 5 or fewer | Proposed: accept 5, skip fewer than 5 unless strong gap | Difference |
| --- | ---: | ---: | ---: |
| First favourite avoided races | 12,808 | 6,934 | -5,874 |
| Missed first-favourite lay wins | 7,615 | 3,746 | -3,869 |
| Avoided first-favourite lay losses | 5,193 | 3,188 | -2,005 |
| Favourite win rate inside avoided races | 40.54% | 45.98% | +5.44 pts |
| Missed lay-win profit | GBP 953.41 | GBP 463.89 | GBP -489.52 |
| Avoided lay-loss liability | GBP 938.79 | GBP 468.05 | GBP -470.74 |
| Net first-favourite guard effect | GBP -14.63 | GBP 4.16 | GBP +18.79 |

## Proposed Rule Reasons

Reason counts overlap, so these rows should not be added together.

| Risk reason | Avoided first-favourite races |
| --- | ---: |
| Probability gap greater than 20% | 4,995 |
| 5-runner race with strong gap | 2,353 |
| Favourite Trap 1 or 2 below 300m | 1,985 |
| Fewer than 5 runners | 948 |

## Missed Lay Wins By Proposed Reason

These are races where the proposed guard avoided the first favourite, but the favourite lost, so a first-favourite lay would have won.

| Risk reason | Missed lay wins | Missed profit |
| --- | ---: | ---: |
| Probability gap greater than 20% | 2,475 | GBP 310.27 |
| Favourite Trap 1 or 2 below 300m | 1,223 | GBP 156.03 |
| 5-runner race with strong gap | 1,166 | GBP 140.40 |
| Fewer than 5 runners | 507 | GBP 57.23 |

## Avoided Lay Losses By Proposed Reason

These are races where the proposed guard avoided the first favourite and the favourite won, so a first-favourite lay would have lost.

| Risk reason | Avoided losses | Avoided liability |
| --- | ---: | ---: |
| Probability gap greater than 20% | 2,520 | GBP 299.16 |
| 5-runner race with strong gap | 1,187 | GBP 133.26 |
| Favourite Trap 1 or 2 below 300m | 762 | GBP 174.42 |
| Fewer than 5 runners | 441 | GBP 54.88 |

## Conclusion

This proposed rule should **not** be applied as-is.

It increases activity a lot, which looks attractive at first:

- 12,167 more bets
- 5,874 more first-favourite bets
- 6,293 fewer skipped races

But the historical Betfair P/L gets much worse:

- P/L drops by GBP 145.76
- max drawdown rises by GBP 144.43
- busts rise from 114 to 222
- fallback P/L worsens by GBP 27.30

The first-favourite avoidance component improves slightly, but the full strategy performs worse once recovery, second-favourite exposure, liabilities, and busts are included.

## Recommendation

Do not simply accept all 5-runner races unless there is a strong gap.

Better next tests:

1. Accept 5-runner races only when favourite odds are above a minimum threshold.
2. Accept 5-runner races only when the probability gap is below 15%, not just below 20%.
3. Accept 5-runner races only when both favourite and second favourite are not Trap 1/2 in sprints.
4. Test 5-runner races as first-favourite-only, with no second-favourite fallback.
