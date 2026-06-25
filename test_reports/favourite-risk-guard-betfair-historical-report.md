# Favourite Risk Guard Betfair Historical Report

Generated: 2026-06-18

## Purpose

Run the same old-vs-new Favourite Risk Guard comparison against the Betfair historical greyhound data in:

`C:\Users\nib8\Downloads\data.tar`

This uses actual settled Betfair WIN markets from the archive, BSP odds, actual winning runner, runner count, parsed distance, market commission where available, recovery-chain staking, variable odds, and actual lay liability.

## Data Loaded

| Metric | Result |
| --- | ---: |
| Archive members scanned | 156,891 |
| Market files scanned | 151,275 |
| WIN markets found | 43,830 |
| UK/IE settled snapshots used | 20,806 |
| Non-UK/IE markets skipped | 22,493 |

The loaded UK/IE snapshots in this archive are labelled as GB venues in the Betfair market definitions.

## Test Setup

- Stake: `0.05`
- Favourites configured: `2`
- Commission: market base rate from Betfair, falling back to `5%`
- Max recovery level: `3`
- Max liability cap: `5.00`
- Previous guard: probability gap greater than `10%`, plus Trap 1/2 favourites on all race distances
- Revised guard: probability gap greater than `20%`, plus Trap 1/2 favourites only below `300m`
- Second-favourite fallback remains blocked where the second favourite is Trap 1 or 2 below `300m`

## P/L Comparison

| Metric | Previous 10% + all Trap 1/2 | Revised 20% + sprint Trap 1/2 | Difference |
| --- | ---: | ---: | ---: |
| Total guard P/L | GBP 55.05 | GBP 12.40 | GBP -42.66 |
| Maximum drawdown | GBP 62.12 | GBP 55.79 | GBP -6.34 |
| Busts | 76 | 114 | +38 |
| Total guard bets | 14,547 | 18,679 | +4,132 |
| First-favourite bets placed | 4,109 | 7,998 | +3,889 |
| Second-favourite bets placed | 10,438 | 10,681 | +243 |
| Fallback second-favourite bets | 6,329 | 2,683 | -3,646 |
| No-bet skips | 10,368 | 10,125 | -243 |
| Fallback P/L | GBP -7.86 | GBP -32.23 | GBP -24.36 |

## First-Favourite Guard Comparison

| Metric | Previous 10% + all Trap 1/2 | Revised 20% + sprint Trap 1/2 | Difference |
| --- | ---: | ---: | ---: |
| First favourite avoided races | 16,697 | 12,808 | -3,889 |
| Missed first-favourite lay wins | 10,138 | 7,615 | -2,523 |
| Avoided first-favourite lay losses | 6,559 | 5,193 | -1,366 |
| Favourite win rate inside avoided races | 39.28% | 40.54% | +1.26 pts |
| Missed first-favourite lay-win profit | GBP 1,289.51 | GBP 953.41 | GBP -336.10 |
| Avoided first-favourite lay-loss liability | GBP 1,298.49 | GBP 938.79 | GBP -359.70 |
| Net first-favourite guard effect | GBP 8.97 | GBP -14.63 | GBP -23.60 |

Interpretation: in the historical data, the old stricter first-favourite avoidance had a small positive first-favourite avoidance effect. The revised guard missed fewer winning lays, which is good, but it also stopped avoiding slightly more losing liability than it regained in winning lays.

## Revised Guard Reasons

Reason counts overlap, so these rows should not be added together.

| Risk reason | Avoided first-favourite races |
| --- | ---: |
| Small field, 5 or fewer runners | 9,695 |
| Probability gap greater than 20% | 4,995 |
| Favourite Trap 1 or 2 below 300m | 1,985 |

| Reason combination | Races |
| --- | ---: |
| Small field only | 6,394 |
| Probability gap only | 1,973 |
| Sprint Trap 1/2 only | 855 |
| Probability gap + small field | 2,456 |
| Sprint Trap 1/2 + small field | 564 |
| Probability gap + sprint Trap 1/2 | 285 |
| Probability gap + sprint Trap 1/2 + small field | 281 |

## Missed Lay Wins By Revised Reason

These are races where the revised guard avoided the first favourite, but the favourite lost, so a first-favourite lay would have won.

| Risk reason | Missed lay wins | Missed profit |
| --- | ---: | ---: |
| Small field, 5 or fewer runners | 5,888 | GBP 727.98 |
| Probability gap greater than 20% | 2,475 | GBP 310.27 |
| Favourite Trap 1 or 2 below 300m | 1,223 | GBP 156.03 |

Because reasons overlap, these values are diagnostic only and do not sum to the headline total.

## Avoided Lay Losses By Revised Reason

These are races where the revised guard avoided the first favourite and the favourite won, so a first-favourite lay would have lost.

| Risk reason | Avoided losses | Avoided liability |
| --- | ---: | ---: |
| Small field, 5 or fewer runners | 3,807 | GBP 696.20 |
| Probability gap greater than 20% | 2,520 | GBP 299.16 |
| Favourite Trap 1 or 2 below 300m | 762 | GBP 174.42 |

Because reasons overlap, these values are diagnostic only and do not sum to the headline total.

## Conclusion

The Betfair historical data disagrees with the synthetic simulator in an important way:

- Simulator: revised guard improved total P/L by `GBP 186.95`.
- Betfair historical data: revised guard reduced total P/L by `GBP 42.66`.

The revised guard still has benefits:

1. It placed 3,889 more first-favourite bets.
2. It cut fallback bets by 3,646.
3. It reduced max drawdown by `GBP 6.34`.
4. It reduced missed first-favourite lay wins by 2,523.

But on actual historical P/L, the previous stricter guard performed better in this data set. The major issue is the small-field rule: 9,695 of 20,806 races were still skipped because they had 5 or fewer runners, and that rule dominates the report.

Recommended next test:

1. Keep the revised 20% gap and sprint-only Trap 1/2 rule.
2. Separately test relaxing or replacing the 5-or-fewer-runners skip.
3. Compare four historical variants: old strict, revised guard, revised without small-field skip, and revised with small-field skip only when probability gap is also above 20%.
