# Weekly P&L - Elastic £75 vs Current

Rules: favourite gap <=10%, second favourite gap 5%-30%, sprint Trap 1/2 exclusion ON, base stake £0.05, 5% commission.
Elastic model: debt-band recovery with £75 liability cap.

## Elastic £75 Totals

- Weeks covered: 76
- Opportunities: 34,311 (12,658 favourite, 21,653 second favourite)
- Net P/L: £284.03
- ROI: 0.96%
- Busts: 28 (11 favourite, 17 second favourite)
- Worst weekly drawdown: £422.36
- Max liability: £75.00

## Key Weeks

- Best week: 2025-W03 (2025-01-13 to 2025-01-19) - £136.25, ROI 4.08%, busts 0
- Worst week: 2025-W02 (2025-01-06 to 2025-01-12) - -£106.39, ROI -29.08%, busts 0
- Most volatile week: 2025-W08 (2025-02-17 to 2025-02-23) - worst drawdown £422.36, net P/L £15.58

## Current vs Elastic £75

- Elastic improved P/L in 24 weeks.
- Elastic worsened P/L in 26 weeks.
- Unchanged weeks: 26.

### Top Elastic Improvements

| Week | Current P/L | Elastic P/L | Delta | Current Max Liability | Elastic Max Liability |
|---|---:|---:|---:|---:|---:|
| 2025-W03 (2025-01-13 to 2025-01-19) | £32.05 | £136.25 | £104.19 | £62.81 | £75.00 |
| 2025-W18 (2025-04-28 to 2025-05-04) | -£99.69 | -£52.40 | £47.29 | £94.88 | £47.54 |
| 2025-W24 (2025-06-09 to 2025-06-15) | -£117.40 | -£71.56 | £45.84 | £81.78 | £40.98 |
| 2025-W17 (2025-04-21 to 2025-04-27) | -£110.30 | -£69.61 | £40.68 | £67.79 | £38.55 |
| 2025-W33 (2025-08-11 to 2025-08-17) | -£61.28 | -£35.33 | £25.96 | £44.20 | £22.16 |
| 2025-W21 (2025-05-19 to 2025-05-25) | £16.57 | £41.58 | £25.01 | £12.02 | £57.74 |
| 2025-W13 (2025-03-24 to 2025-03-30) | -£67.64 | -£51.55 | £16.08 | £44.56 | £33.46 |
| 2025-W31 (2025-07-28 to 2025-08-03) | -£44.43 | -£33.70 | £10.73 | £35.38 | £26.57 |
| 2025-W46 (2025-11-10 to 2025-11-16) | -£36.83 | -£26.61 | £10.22 | £41.46 | £31.14 |
| 2025-W42 (2025-10-13 to 2025-10-19) | -£17.85 | -£8.35 | £9.50 | £27.61 | £34.54 |

### Top Elastic Worsening Weeks

| Week | Current P/L | Elastic P/L | Delta | Current Closing Debt | Elastic Closing Debt |
|---|---:|---:|---:|---:|---:|
| 2025-W02 (2025-01-06 to 2025-01-12) | -£0.06 | -£106.39 | -£106.33 | £15.02 | £121.26 |
| 2025-W20 (2025-05-12 to 2025-05-18) | £15.24 | -£12.86 | -£28.10 | £0.00 | £25.25 |
| 2025-W41 (2025-10-06 to 2025-10-12) | £17.67 | £14.70 | -£2.97 | £0.00 | £2.78 |
| 2025-W08 (2025-02-17 to 2025-02-23) | £17.29 | £15.58 | -£1.71 | £0.19 | £0.19 |
| 2025-W07 (2025-02-10 to 2025-02-16) | £17.47 | £16.90 | -£0.57 | £0.00 | £0.00 |
| 2025-W04 (2025-01-20 to 2025-01-26) | £17.88 | £17.55 | -£0.33 | £0.00 | £0.00 |
| 2026-W16 (2026-04-13 to 2026-04-19) | £15.69 | £15.36 | -£0.33 | £0.00 | £0.00 |
| 2025-W25 (2025-06-16 to 2025-06-22) | £15.72 | £15.44 | -£0.28 | £0.00 | £0.00 |
| 2025-W51 (2025-12-15 to 2025-12-21) | £17.90 | £17.62 | -£0.28 | £0.00 | £0.00 |
| 2026-W22 (2026-05-25 to 2026-05-31) | £14.09 | £13.90 | -£0.19 | £0.16 | £0.16 |

## Repeated Bad Seasonal Periods

- Month 01: 3 losing weeks, Elastic net P/L -£139.29, busts 2
- Month 04: 4 losing weeks, Elastic net P/L -£139.28, busts 5
- Month 06: 2 losing weeks, Elastic net P/L -£86.11, busts 3
- Month 08: 3 losing weeks, Elastic net P/L -£73.44, busts 4
- Month 03: 2 losing weeks, Elastic net P/L -£56.60, busts 3

## Output Files

- `test_reports/layhounds_weekly_pnl_elastic75/weekly_pnl_elastic75.csv`
- `test_reports/layhounds_weekly_pnl_elastic75/weekly_pnl_current_vs_elastic75.csv`
- `test_reports/layhounds_weekly_pnl_elastic75/weekly_pnl_summary.md`

Note: weekly recovery state is continuous across week boundaries. Weekly P/L is grouped by race off-time ISO week; closing recovery debt is the outstanding chain debt after the final qualifying opportunity in that week.
