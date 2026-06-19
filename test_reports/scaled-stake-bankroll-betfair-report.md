# Scaled Stake Bankroll Betfair Report

Generated: 2026-06-18

## Purpose

Redo the daily historical parameter test with the risk controls scaled to stake.

The previous grid used the same stop-loss and liability caps across all stakes. That made higher stakes unfairly fragile. This test scales the daily stop-win, stop-loss, and liability cap with the base stake so higher-stake settings have proportionally larger bankroll room.

## Data Loaded

| Metric | Result |
| --- | ---: |
| Archive | `C:\Users\nib8\Downloads\data.tar` |
| WIN markets found | 43,830 |
| UK/IE settled snapshots used | 20,806 |
| Historical race days | 161 |
| Non-UK/IE markets skipped | 22,493 |

Each historical day was replayed as a fresh daily session.

## Risk Guard Used

The run used the current revised Favourite Risk Guard:

- skip/fallback when favourite probability gap is greater than 20%
- skip/fallback when favourite is Trap 1 or 2 below 300m
- skip races with 5 or fewer runners
- block the second-favourite fallback when the second favourite is Trap 1 or 2 below 300m

## Scaled Grid

| Parameter | Values Tested |
| --- | --- |
| Base stake | `0.05`, `0.10`, `0.25`, `0.50` |
| Recovery level | `1`, `2`, `3`, `4`, `5` |
| Liability cap | `100x stake`, `200x stake` |
| Stop-win | `40x stake`, `100x stake` |
| Stop-loss | `100x stake`, `200x stake` |
| Total configurations tested | 160 |

Example scaling:

| Stake | Stop-win options | Stop-loss options | Liability cap options |
| ---: | ---: | ---: | ---: |
| GBP 0.05 | GBP 2 / GBP 5 | GBP 5 / GBP 10 | GBP 5 / GBP 10 |
| GBP 0.10 | GBP 4 / GBP 10 | GBP 10 / GBP 20 | GBP 10 / GBP 20 |
| GBP 0.25 | GBP 10 / GBP 25 | GBP 25 / GBP 50 | GBP 25 / GBP 50 |
| GBP 0.50 | GBP 20 / GBP 50 | GBP 50 / GBP 100 | GBP 50 / GBP 100 |

Full CSV results were exported to:

`test_reports/scaled-stake-grid-results.csv`

## Headline Answer

Yes, higher stakes did scale profit when the bankroll controls scaled with them.

The best `GBP 0.50` configuration produced roughly 10x the P/L of the best `GBP 0.05` configuration, but also roughly 10x the daily drawdown and worst-day exposure.

| Stake | Best Matching Setup | Total P/L | Avg/day | Worst day | Max daily DD | Win days | Busts |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GBP 0.05 | L5, cap 10, SW 5, SL 10 | GBP 119.15 | GBP 0.74 | GBP -10.00 | GBP 13.94 | 77.64% | 15 |
| GBP 0.10 | L5, cap 20, SW 10, SL 20 | GBP 238.24 | GBP 1.48 | GBP -20.00 | GBP 27.89 | 77.64% | 13 |
| GBP 0.25 | L5, cap 50, SW 25, SL 50 | GBP 595.74 | GBP 3.70 | GBP -50.00 | GBP 69.71 | 77.64% | 15 |
| GBP 0.50 | L5, cap 100, SW 50, SL 100 | GBP 1,191.27 | GBP 7.40 | GBP -100.00 | GBP 139.43 | 77.64% | 15 |

This is almost perfectly proportional scaling. The earlier poor high-stake results happened because the stake was increased without giving the strategy proportional stop-loss and liability room.

## Best By Total P/L

| Rank | Stake | Recovery | Cap | Stop-win | Stop-loss | Total P/L | Avg/day | Win days | Worst day | Max daily DD | Busts |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | GBP 0.50 | L5 | GBP 100 | GBP 50 | GBP 100 | GBP 1,191.27 | GBP 7.40 | 77.64% | GBP -100.00 | GBP 139.43 | 15 |
| 2 | GBP 0.50 | L4 | GBP 100 | GBP 50 | GBP 100 | GBP 973.42 | GBP 6.05 | 76.40% | GBP -100.00 | GBP 142.28 | 35 |
| 3 | GBP 0.50 | L5 | GBP 100 | GBP 20 | GBP 100 | GBP 673.64 | GBP 4.18 | 85.71% | GBP -100.00 | GBP 119.95 | 9 |
| 4 | GBP 0.25 | L5 | GBP 50 | GBP 25 | GBP 50 | GBP 595.74 | GBP 3.70 | 77.64% | GBP -50.00 | GBP 69.71 | 15 |
| 5 | GBP 0.50 | L4 | GBP 100 | GBP 20 | GBP 100 | GBP 506.81 | GBP 3.15 | 85.09% | GBP -100.00 | GBP 119.95 | 21 |

## Best Risk-Adjusted Pattern

The risk-adjusted result is the important part. The best pattern was essentially the same across stakes:

- recovery level: `L5`
- liability cap: `200x stake`
- stop-win: `100x stake`
- stop-loss: `200x stake`

| Stake | Total P/L | Max daily DD | P/L per max DD |
| ---: | ---: | ---: | ---: |
| GBP 0.05 | GBP 119.15 | GBP 13.94 | 8.5457 |
| GBP 0.10 | GBP 238.24 | GBP 27.89 | 8.5436 |
| GBP 0.25 | GBP 595.74 | GBP 69.71 | 8.5456 |
| GBP 0.50 | GBP 1,191.27 | GBP 139.43 | 8.5442 |

That means the system scales, but risk scales with it. Bigger stake did not create a better edge; it created a bigger version of the same edge and the same drawdown profile.

## Important Caveat

The best `GBP 0.50` setup has:

- worst historical day near `GBP -100`
- max daily drawdown around `GBP 139`
- stop-loss of `GBP 100`
- liability cap of `GBP 100`

So it needs a much larger bankroll and risk tolerance than the `GBP 0.05` setup. It is not safer, just larger.

## What Still Failed

Some scaled higher-stake settings still performed badly when the cap/stop relationship was poor.

Worst example:

| Stake | Recovery | Cap | Stop-win | Stop-loss | Total P/L | Avg/day | Max daily DD |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GBP 0.50 | L3 | GBP 50 | GBP 20 | GBP 100 | GBP -856.60 | GBP -5.32 | GBP 116.15 |

This shows that scaling alone is not enough. The ratio between stop-win, stop-loss, liability cap, and recovery depth matters.

## Conclusion

Your expectation was correct: higher stakes can produce larger profit when the starting bank and risk controls scale with them.

The previous report made higher stakes look worse because the stop-loss and liability cap were too tight relative to stake.

The best historical scaling pattern from this run was:

- stake: user-selectable
- recovery level: `L5`
- liability cap: `200x stake`
- stop-win: `100x stake`
- stop-loss: `200x stake`

For example:

| Stake | Recovery | Cap | Stop-win | Stop-loss |
| ---: | ---: | ---: | ---: | ---: |
| GBP 0.05 | L5 | GBP 10 | GBP 5 | GBP 10 |
| GBP 0.10 | L5 | GBP 20 | GBP 10 | GBP 20 |
| GBP 0.25 | L5 | GBP 50 | GBP 25 | GBP 50 |
| GBP 0.50 | L5 | GBP 100 | GBP 50 | GBP 100 |

## Recommended App Function

LayHounds should not recommend a single stake in isolation. It should recommend a **risk-scaled configuration**:

1. User chooses bankroll or acceptable worst-day loss.
2. App derives stake, stop-win, stop-loss, and liability cap from the same risk multiple.
3. App shows historical replay evidence:
   - total P/L
   - average daily P/L
   - worst day
   - max daily drawdown
   - bust count
   - winning-day percentage
4. User can apply the selected configuration to the simulator/live session.

This would make the app much more useful than fixed presets, because it would keep the ratios consistent as the user scales up.
