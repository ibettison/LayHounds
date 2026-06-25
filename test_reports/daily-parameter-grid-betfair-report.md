# Daily Parameter Grid Betfair Report

Generated: 2026-06-18

## Purpose

Test different LayHounds operating settings against the Betfair historical greyhound data using daily stop-win and stop-loss logic.

This report is intended to identify which combinations of:

- base stake
- recovery level
- liability cap
- stop-win
- stop-loss

performed best against the historical data before changing the app defaults or adding a recommendation function.

## Data Loaded

| Metric | Result |
| --- | ---: |
| Archive | `C:\Users\nib8\Downloads\data.tar` |
| Archive members scanned | 156,891 |
| Market files scanned | 151,275 |
| WIN markets found | 43,830 |
| UK/IE settled snapshots used | 20,806 |
| Historical race days | 161 |
| Non-UK/IE markets skipped | 22,493 |

The archive was replayed by day. Each historical day used a fresh bank/recovery session so stop-win and stop-loss could operate like daily controls.

## Risk Guard Used

The run used the current revised Favourite Risk Guard:

- skip/fallback when favourite probability gap is greater than 20%
- skip/fallback when favourite is Trap 1 or 2 below 300m
- skip races with 5 or fewer runners
- block the second-favourite fallback when the second favourite is Trap 1 or 2 below 300m

The proposed 5-runner relaxation was **not** used because its historical P/L was worse.

## Parameter Grid

| Parameter | Values Tested |
| --- | --- |
| Base stake | `0.05`, `0.10`, `0.25`, `0.50` |
| Recovery level | `1`, `2`, `3`, `4`, `5` |
| Liability cap | `1.00`, `2.50`, `5.00`, `10.00` |
| Stop-win | `0.50`, `1.00`, `2.00`, `5.00` |
| Stop-loss | `1.00`, `2.50`, `5.00`, `10.00` |
| Total configurations tested | 1,280 |

## Best By Total P/L

| Rank | Stake | Recovery | Cap | Stop-win | Stop-loss | Total P/L | Avg/day | Win days | Max daily DD | Busts | Bets |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | GBP 0.05 | L5 | GBP 10.00 | GBP 5.00 | GBP 10.00 | GBP 119.15 | GBP 0.74 | 77.64% | GBP 13.94 | 15 | 16,411 |
| 2 | GBP 0.05 | L4 | GBP 10.00 | GBP 5.00 | GBP 10.00 | GBP 97.33 | GBP 0.60 | 76.40% | GBP 14.23 | 33 | 16,535 |
| 3 | GBP 0.05 | L5 | GBP 10.00 | GBP 2.00 | GBP 10.00 | GBP 67.36 | GBP 0.42 | 85.71% | GBP 12.00 | 8 | 9,235 |
| 4 | GBP 0.05 | L4 | GBP 10.00 | GBP 2.00 | GBP 10.00 | GBP 50.67 | GBP 0.31 | 85.09% | GBP 12.00 | 18 | 9,488 |
| 5 | GBP 0.05 | L3 | GBP 10.00 | GBP 5.00 | GBP 5.00 | GBP 38.04 | GBP 0.24 | 59.63% | GBP 9.37 | 77 | 14,674 |

The best total P/L was:

`Stake GBP 0.05, Recovery L5, Liability Cap GBP 10, Stop-win GBP 5, Stop-loss GBP 10`

It finished:

- GBP 119.15 total P/L
- GBP 0.74 average daily P/L
- 125 winning days out of 161
- 36 losing days
- 77.64% winning days
- worst day about GBP -10.00
- best day about GBP 5.29
- 15 busts

## Best Lower-Risk Candidates

These configurations did not produce the highest total P/L, but they reduced activity or daily downside.

| Candidate | Stake | Recovery | Cap | Stop-win | Stop-loss | Total P/L | Avg/day | Win days | Max daily DD | Busts | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Stronger total P/L | GBP 0.05 | L5 | GBP 10.00 | GBP 5.00 | GBP 10.00 | GBP 119.15 | GBP 0.74 | 77.64% | GBP 13.94 | 15 | Best overall historical P/L |
| More frequent daily lock-in | GBP 0.05 | L5 | GBP 10.00 | GBP 2.00 | GBP 10.00 | GBP 67.36 | GBP 0.42 | 85.71% | GBP 12.00 | 8 | More winning days, fewer bets |
| Lower stop-loss | GBP 0.05 | L3 | GBP 10.00 | GBP 5.00 | GBP 5.00 | GBP 38.04 | GBP 0.24 | 59.63% | GBP 9.37 | 77 | Smaller daily loss setting, but more busts |
| Current-ish safer cap | GBP 0.05 | L3 | GBP 5.00 | GBP 5.00 | GBP 5.00 | GBP 26.31 | GBP 0.16 | 62.11% | GBP 8.94 | 108 | Lower cap, lower P/L |

## What Did Not Work Well

Higher base stakes were not automatically better. Many `GBP 0.50` configurations performed badly, especially with wider stop settings.

Worst example from the grid:

| Stake | Recovery | Cap | Stop-win | Stop-loss | Total P/L | Avg/day | Win days | Max daily DD | Busts |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GBP 0.50 | L1 | GBP 5.00 | GBP 5.00 | GBP 10.00 | GBP -313.86 | GBP -1.95 | 50.31% | GBP 14.75 | 1,161 |

The bigger stake created too much liability pressure and caused substantially worse results.

## Key Findings

1. The best historical result came from the smallest tested stake, `GBP 0.05`.
2. Deeper recovery, especially L4-L5, helped when paired with a wider liability cap and wider stop-loss.
3. A `GBP 10` liability cap performed better than `GBP 5` in the top historical configurations.
4. A lower stop-win such as `GBP 2` increased winning-day percentage, but reduced total P/L.
5. Higher base stakes increased volatility and often made P/L worse.
6. Stop-loss has a strong effect on daily outcome. The best P/L used `GBP 10`, but that accepts larger bad days.

## Recommended App Function

Do not hard-code one â€œbestâ€ setting as a guaranteed optimum. Instead, LayHounds should expose a historical optimiser that:

1. Lets the user choose a Betfair historical data source.
2. Runs a parameter grid over stake, recovery level, liability cap, stop-win, and stop-loss.
3. Reports:
   - total P/L
   - average daily P/L
   - winning-day percentage
   - worst day
   - maximum daily drawdown
   - bust count
   - bets placed
4. Sorts results by:
   - best total P/L
   - best risk-adjusted P/L
   - lowest drawdown
   - highest winning-day percentage
5. Allows the chosen configuration to be copied into a simulator/live session.

The app should present this as â€œhistorical replay evidenceâ€, not a guaranteed profit recommendation.

## Suggested Default Candidate To Test Next

Based on this grid, the best candidate for further testing is:

- stake: `GBP 0.05`
- recovery level: `5`
- liability cap: `GBP 10`
- stop-win: `GBP 5`
- stop-loss: `GBP 10`

But this should be validated again with:

1. a holdout date range,
2. optional monthly breakdowns,
3. historical replay mode inside the simulator,
4. and alternative race filters before becoming a promoted default.
