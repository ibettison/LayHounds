# LayHounds Full-Season Risk and Profitability Report

Source: `C:\Users\nib8\Downloads\data2025.tar`
Included UK/IE races: 49,353

## Executive Summary

- Highest ROI non-runaway configuration: **Favourite <=15% gap** (-0.51% ROI).
- Lowest risk non-runaway configuration: **Conservative** (18 busts, worst drawdown £258.3695).
- Best profit-to-risk configuration: **Favourite <=15% gap**.
- Favourite <=10% and Second Favourite 5%-30% validation: **Yes, it improves ROI and reduces bust/drawdown versus Current**
- Runaway threshold for reporting: per-bet liability > £1,000,000. Runaway rows are not treated as valid final configurations.

## Baseline

| Rule Set | Opps | Net P/L | ROI | Busts | Worst Bust DD | Max Liability | Runaways |
|---|---:|---:|---:|---:|---:|---:|---:|
| No filters | 98,706 | £-652.1067 | -1.3% | 232 | £175.9535 | £192.443 | 0 |
| Current LayHounds rules | 57,243 | £-486.1877 | -1.35% | 44 | £140.5565 | £159.7198 | 0 |

## Recommended Modes

| Mode | Rules | Opps | Net P/L | ROI | Busts | Worst DD | Max Liability |
|---|---|---:|---:|---:|---:|---:|---:|
| Conservative | Fav <=5%, 2nd 5-20%, sprint ON | 15,620 | £-154.3823 | -1.91% | 18 | £258.3695 | £66.9514 |
| Balanced | Fav <=10%, 2nd 5-30%, sprint ON | 24,478 | £-170.5838 | -1.29% | 22 | £466.8946 | £94.8793 |
| Aggressive | Fav <=15%, 2nd 5-40%, sprint ON | 31,861 | £-192.5564 | -1.09% | 31 | £424.3379 | £81.7795 |

## Files

- `baseline.csv`, `filter_validation.csv`, `grade_analysis.csv`, `venue_analysis.csv`
- `gap_analysis.csv`, `trap_analysis.csv`, `recovery_busts.csv`, `walk_forward.csv`
- `final_recommendations.csv`, `summary.json`
