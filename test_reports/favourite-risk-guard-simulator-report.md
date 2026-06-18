# Favourite Risk Guard Simulator Report

Generated: 2026-06-18

## Purpose

Compare the previous strict Favourite Risk Guard with the revised guard:

- previous guard: probability gap greater than 10%, plus Trap 1/2 favourites on all race distances
- revised guard: probability gap greater than 20%, plus Trap 1/2 favourites only below 300m
- second-favourite fallback remains blocked when the second favourite is Trap 1 or 2 below 300m

Both runs use the same LayHounds simulator race generator, winner picker, recovery-chain logic, Betfair commission on winning lay bets, liability caps, seed, race count, and stake settings.

## Simulation Setup

- Seed: `20260618`
- Races simulated: `50,000`
- Mode: simulator
- Stake: `0.05`
- Favourites configured: `2`
- Risk guard: `strict`
- Commission: `5%`
- Max recovery level: `3`
- Max liability cap: `5.00`

Note: this is a long-run simulator sample. It does not prove real-market profitability, and it should not be mixed with historical Betfair results.

## Headline Comparison

| Metric | Previous 10% + all Trap 1/2 | Revised 20% + sprint Trap 1/2 | Difference |
| --- | ---: | ---: | ---: |
| First favourite avoided races | 44,109 | 21,290 | -22,819 |
| First favourite bets placed | 5,891 | 28,710 | +22,819 |
| Missed first-favourite lay wins | 28,655 | 13,552 | -15,103 |
| Avoided first-favourite lay losses | 15,454 | 7,738 | -7,716 |
| Favourite win rate inside avoided races | 35.04% | 36.35% | +1.31 pts |
| Missed first-favourite lay-win profit | GBP 3,155.34 | GBP 1,485.81 | GBP -1,669.53 |
| Avoided first-favourite lay-loss liability | GBP 2,557.43 | GBP 993.75 | GBP -1,563.68 |
| Net first-favourite guard effect | GBP -597.91 | GBP -492.06 | GBP +105.85 |
| Fallback second-favourite bets | 43,541 | 20,948 | -22,593 |
| No-bet skips | 568 | 342 | -226 |
| Fallback P/L | GBP -1,172.45 | GBP -1,041.10 | GBP +131.35 |
| Total guard P/L | GBP -1,302.28 | GBP -1,115.33 | GBP +186.95 |

## Revised Guard Results

| Metric | Result |
| --- | ---: |
| Races where first favourite was avoided | 21,290 |
| Missed first-favourite lay wins | 13,552 |
| Avoided first-favourite lay losses | 7,738 |
| Favourite win rate inside avoided races | 36.35% |
| Favourite loss rate inside avoided races | 63.65% |
| Profit missed from first-favourite lay wins | GBP 1,485.81 |
| Liability avoided from first-favourite lay losses | GBP 993.75 |
| Net first-favourite guard effect in simulator sample | GBP -492.06 |

Interpretation: the revised guard is a clear improvement over the previous strict setting in this synthetic simulator sample. It reduced missed first-favourite lay wins by 15,103 and improved total simulated P/L by GBP 186.95. It still remains negative overall in the simulator sample, so it should be treated as a risk-control improvement rather than proof of profitability.

## Revised Risk Reasons

Reason counts overlap, so these rows should not be added together.

| Risk reason | Avoided first-favourite races |
| --- | ---: |
| Probability gap greater than 20% | 20,921 |
| Favourite in Trap 1 or 2 below 300m | 661 |

| Reason combination | Races |
| --- | ---: |
| Probability gap only | 20,629 |
| Sprint Trap 1/2 only | 369 |
| Probability gap and sprint Trap 1/2 | 292 |

## Missed Lay Wins By Reason

These are races where the risk guard avoided the first favourite, but the favourite lost, so a first-favourite lay would have won.

| Risk reason | Missed lay wins | Missed profit |
| --- | ---: | ---: |
| Probability gap greater than 20% | 13,325 | GBP 1,461.00 |
| Favourite in Trap 1 or 2 below 300m | 407 | GBP 42.26 |

Because reasons overlap, the missed profit by reason is diagnostic only and does not sum to the headline total.

## Avoided Lay Losses By Reason

These are races where the risk guard avoided the first favourite and the favourite won, so a first-favourite lay would have lost.

| Risk reason | Avoided losses | Avoided liability |
| --- | ---: | ---: |
| Probability gap greater than 20% | 7,596 | GBP 954.57 |
| Favourite in Trap 1 or 2 below 300m | 254 | GBP 57.42 |

Because reasons overlap, the avoided liability by reason is diagnostic only and does not sum to the headline total.

## Revised Second-Favourite Fallback Results

| Metric | Result |
| --- | ---: |
| Total guard bets placed | 78,368 |
| First-favourite bets placed | 28,710 |
| Second-favourite bets placed | 49,658 |
| Second-favourite fallback bets | 20,948 |
| Fallback wins | 16,342 |
| Fallback losses | 4,606 |
| Fallback liability risked | GBP 15,878.27 |
| Fallback P/L | GBP -1,041.10 |
| No-bet skips | 342 |
| Blocked second-favourite sprint fallbacks | 342 |

## Conclusion

The revised 20% + sprint-only Trap 1/2 guard is better than the previous strict guard in the simulator:

1. It missed far fewer first-favourite lay wins.
2. It placed 22,819 more first-favourite bets.
3. It reduced fallback volume by 22,593 races.
4. It improved overall simulated P/L by GBP 186.95.

The key caveat is that the simulator still shows negative P/L for both versions. The next best step is to run the same comparison against the UK/IE Betfair historical data, because the real price and winner distribution matters more than the synthetic generator.

