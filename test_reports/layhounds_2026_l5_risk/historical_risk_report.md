# LayHounds 2026 UK/IE L5 Recovery-Chain Risk Report

Source archive: `C:\Users\nib8\Downloads\data.tar`
Output directory: `test_reports\layhounds_2026_l5_risk`

## Scope

- Archive members scanned: 156,891
- Betfair market files scanned: 151,275
- UK/IE closed WIN races included: 20,806
- Bust definition: five consecutive backed winners against the same lay chain.
- Favourite and second-favourite chains are simulated independently.
- Skipped selections do not advance or reset a chain.

## Scenario Summary

| Scenario | Chain | Bets | Retained | Busts | Bust reduction | Bet reduction |
|---|---:|---:|---:|---:|---:|---:|
| No filters | favourite | 20,806 | 100.00% | 99 | 0.00% | 0.00% |
| No filters | second_favourite | 20,806 | 100.00% | 15 | 0.00% | 0.00% |
| 15% variance only | favourite | 5,505 | 26.46% | 5 | 94.95% | 73.54% |
| 15% variance only | second_favourite | 20,806 | 100.00% | 15 | 0.00% | 0.00% |
| Sprint Trap 1/2 only | favourite | 18,774 | 90.23% | 86 | 13.13% | 9.77% |
| Sprint Trap 1/2 only | second_favourite | 18,623 | 89.51% | 8 | 46.67% | 10.49% |
| 15% variance + sprint Trap 1/2 | favourite | 4,997 | 24.02% | 6 | 93.94% | 75.98% |
| 15% variance + sprint Trap 1/2 | second_favourite | 18,623 | 89.51% | 8 | 46.67% | 10.49% |
| Both rules + odds >= 2.0 | favourite | 4,995 | 24.01% | 6 | 93.94% | 75.99% |
| Both rules + odds >= 2.0 | second_favourite | 18,623 | 89.51% | 8 | 46.67% | 10.49% |
| Both rules + venue filters (Newcastle (GB), Sheffield (GB), Valley (GB), Yarmouth (GB)) | favourite | 3,960 | 19.03% | 1 | 98.99% | 80.97% |
| Both rules + venue filters (Newcastle (GB), Sheffield (GB), Valley (GB), Yarmouth (GB)) | second_favourite | 14,581 | 70.08% | 3 | 80.00% | 29.92% |
| Both rules + grade filters (A1, A7, A8, A9, D5) | favourite | 3,813 | 18.33% | 3 | 96.97% | 81.67% |
| Both rules + grade filters (A1, A7, A8, A9, D5) | second_favourite | 14,512 | 69.75% | 2 | 86.67% | 30.25% |

## Strongest Filters

- The combined variance + sprint-inside rule leaves 6 favourite busts and 8 second-favourite busts while retaining 24.02% / 89.51% of opportunities.
- Adding odds >= 2.0 leaves 6 favourite busts and 8 second-favourite busts, retaining 24.01% / 89.51%.
- Balanced venue filter set selected: Newcastle (GB), Sheffield (GB), Valley (GB), Yarmouth (GB).
- Balanced grade filter set selected: A1, A7, A8, A9, D5.
- Exhaustive venue search over bust-source venues bottoms out at 3 remaining busts with 38.54% fewer bets.
- Exhaustive grade search over bust-source grades bottoms out at 3 remaining busts with 37.13% fewer bets.

## Recommended 2026 Defaults

1. Keep the 15% favourite variance rule enabled for the favourite chain.
2. Keep the sprint Trap 1/2 skip enabled for both favourite and second-favourite chains.
3. Keep odds >= 2.0 enabled at least for the favourite chain; it is cheap insurance against very short-priced favourites.
4. Consider venue exclusions only as a higher-risk mode toggle: Newcastle (GB), Sheffield (GB), Valley (GB), Yarmouth (GB).
5. Consider grade exclusions only if you accept the opportunity loss: A1, A7, A8, A9, D5.

## Top Venue Bust Sources After Both Core Rules

| Chain | Venue | Busts | Qualified bets | Busts / 1000 bets |
|---|---|---:|---:|---:|
| favourite | Sheffield (GB) | 2 | 226 | 8.85 |
| second_favourite | Oxford (GB) | 2 | 544 | 3.676 |
| second_favourite | Romford (GB) | 2 | 1608 | 1.244 |
| favourite | Yarmouth (GB) | 1 | 257 | 3.891 |
| favourite | Sunderland (GB) | 1 | 347 | 2.882 |
| favourite | Newcastle (GB) | 1 | 366 | 2.732 |
| favourite | Romford (GB) | 1 | 441 | 2.268 |
| second_favourite | Valley (GB) | 1 | 824 | 1.214 |
| second_favourite | Doncaster (GB) | 1 | 1054 | 0.949 |
| second_favourite | Sunderland (GB) | 1 | 1270 | 0.787 |
| second_favourite | Newcastle (GB) | 1 | 1339 | 0.747 |

## Top Grade Bust Sources After Both Core Rules

| Chain | Grade | Busts | Qualified bets | Busts / 1000 bets |
|---|---|---:|---:|---:|
| favourite | A4 | 3 | 986 | 3.043 |
| second_favourite | A4 | 3 | 3890 | 0.771 |
| favourite | A7 | 2 | 433 | 4.619 |
| favourite | A8 | 1 | 243 | 4.115 |
| second_favourite | A9 | 1 | 405 | 2.469 |
| second_favourite | A1 | 1 | 688 | 1.453 |
| second_favourite | D5 | 1 | 708 | 1.412 |
| second_favourite | A3 | 1 | 1363 | 0.734 |
| second_favourite | A6 | 1 | 1561 | 0.641 |

## Files

- `summary.json` and `scenario_summary.csv`: headline scenario results.
- `bust_events.csv`: every L5 bust event with race, chain, trap, venue, grade, distance and odds-gap context.
- `daily_bust_counts.csv`, `venue_bust_counts.csv`, `grade_bust_counts.csv`, `distance_band_bust_counts.csv`, `trap_bust_counts.csv`, `odds_gap_band_bust_counts.csv`: requested breakdowns.
- `venue_filter_candidates.csv` and `grade_filter_candidates.csv`: per-value filter trade-off inputs.
- `venue_filter_tradeoffs.csv` and `grade_filter_tradeoffs.csv`: exhaustive combinations over bust-source values.
