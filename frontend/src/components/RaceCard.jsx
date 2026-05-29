import React from "react";
import { Trophy, Target } from "lucide-react";

const TrapBadge = ({ trap }) => (
  <div
    className={`trap-${trap} w-9 h-9 flex items-center justify-center font-mono font-bold text-lg`}
    data-testid={`trap-badge-${trap}`}
  >
    {trap}
  </div>
);

const formatRaceTime = (race) => {
  const raw = race?.market_start_time || race?.timestamp;
  if (!raw) return null;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
};

export const RaceCard = ({ race, layedRanks }) => {
  if (!race) {
    return (
      <div className="bg-[#141414] border border-[#2A2A2A] p-12 text-center">
        <Target className="w-12 h-12 mx-auto text-zinc-700 mb-3" />
        <div className="font-display text-2xl uppercase tracking-tight text-zinc-400">
          No race yet
        </div>
        <div className="text-sm text-zinc-500 mt-2">
          Click "Run Next Race" to simulate the first event.
        </div>
      </div>
    );
  }

  const sorted = [...race.runners].sort((a, b) => a.favourite_rank - b.favourite_rank);
  const betsByRank = {};
  for (const b of race.bets) betsByRank[b.favourite_rank] = b;
  const raceTime = formatRaceTime(race);

  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="race-card">
      <div className="flex items-center justify-between bg-[#0A0A0A] border-b border-[#2A2A2A] p-4">
        <div>
          <div className="label-xs">Race #{race.race_num}</div>
          <div className="flex items-baseline gap-2 min-w-0">
            <span className="font-display text-2xl uppercase tracking-tight truncate">{race.venue}</span>
            {raceTime && (
              <span className="font-display text-2xl uppercase tracking-tight text-zinc-500 shrink-0">
                {raceTime}
              </span>
            )}
          </div>
          {race.category && (
            <div className="flex items-center gap-1.5 mt-1.5" data-testid="race-category">
              <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider bg-pink-500/15 text-pink-300 border border-pink-500/30">
                {race.category.grade}
              </span>
              <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider bg-zinc-700/40 text-zinc-300 border border-zinc-600/40">
                {race.category.distance_m}m
              </span>
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                {race.category.distance_band_label}
              </span>
            </div>
          )}
        </div>
        <div className="text-right">
          <div className="label-xs">P&amp;L Change</div>
          <div
            className={`font-mono text-2xl font-bold ${
              race.pnl_change >= 0 ? "text-emerald-400" : "text-red-400"
            }`}
            data-testid="race-pnl-change"
          >
            {race.pnl_change >= 0 ? "+" : ""}£{Number(race.pnl_change || 0).toFixed(2)}
          </div>
        </div>
      </div>

      <table className="w-full">
        <thead>
          <tr className="bg-[#1C1C1C] text-xs uppercase tracking-wider text-zinc-400">
            <th className="p-3 text-left">Trap</th>
            <th className="p-3 text-left">Greyhound</th>
            <th className="p-3 text-left">Rank</th>
            <th className="p-3 text-right">Odds</th>
            <th className="p-3 text-right">Lay Bet</th>
            <th className="p-3 text-center">Result</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const bet = betsByRank[r.favourite_rank];
            const isWinner = r.trap === race.winning_trap;
            const isLayed = layedRanks.includes(r.favourite_rank);
            return (
              <tr
                key={r.trap}
                data-testid={`race-row-${r.trap}`}
                className={`border-b border-[#2A2A2A] ${
                  isWinner ? "bg-emerald-500/10" : ""
                } ${isLayed && !isWinner ? "bg-pink-500/5" : ""}`}
              >
                <td className="p-3">
                  <TrapBadge trap={r.trap} />
                </td>
                <td className="p-3">
                  <div className="font-medium flex items-center gap-2">
                    {r.name}
                    {isWinner && <Trophy className="w-4 h-4 text-emerald-400" />}
                  </div>
                </td>
                <td className="p-3">
                  {isLayed ? (
                    <span className="bg-pink-500/10 border border-pink-500/30 text-pink-400 px-2 py-0.5 text-xs font-bold uppercase tracking-wider">
                      Fav #{r.favourite_rank}
                    </span>
                  ) : (
                    <span className="text-zinc-500 text-xs font-mono">#{r.favourite_rank}</span>
                  )}
                </td>
                <td className="p-3 text-right font-mono text-base">{Number(r.odds || 0).toFixed(2)}</td>
                <td className="p-3 text-right font-mono text-sm">
                  {bet ? (
                    <div>
                      <div className="text-pink-400">£{Number(bet.stake || 0).toFixed(2)}</div>
                      <div className="text-amber-400/80 text-xs">
                        liab £{Number(bet.liability || 0).toFixed(2)}
                      </div>
                      {bet.matched_size != null && bet.matched_price != null && (
                        <div className="text-emerald-400/70 text-[10px] mt-0.5 font-mono flex items-center gap-1.5">
                          <span>matched £{Number(bet.matched_size || 0).toFixed(2)} @{Number(bet.matched_price || 0).toFixed(2)}</span>
                          {bet.slippage_ticks != null && bet.slippage_ticks !== 0 && (
                            <span
                              data-testid={`slippage-${r.favourite_rank}`}
                              title={bet.slippage_ticks > 0
                                ? `Price drifted ${bet.slippage_ticks} tick(s) HIGHER than requested — more liability per matched £`
                                : `Price steamed ${Math.abs(bet.slippage_ticks)} tick(s) LOWER than requested — better lay than asked`}
                              className={`px-1 py-0 text-[9px] font-bold uppercase tracking-wider border ${
                                bet.slippage_ticks > 0
                                  ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                                  : "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                              }`}
                            >
                              {bet.slippage_ticks > 0 ? `+${bet.slippage_ticks}T` : `${bet.slippage_ticks}T`}
                            </span>
                          )}
                        </div>
                      )}
                      {bet.placement_status === "unmatched" && (
                        <div className="text-zinc-500 text-[10px] mt-0.5 font-mono uppercase tracking-wider">
                          unmatched
                        </div>
                      )}
                      {bet.placement_status === "partial" && (
                        <div className="text-amber-400 text-[10px] mt-0.5 font-mono uppercase tracking-wider">
                          partial
                        </div>
                      )}
                      {bet.chase_attempts > 1 && (
                        <div className="text-amber-300/80 text-[10px] mt-0.5 font-mono uppercase tracking-wider">
                          chased {bet.chase_attempts}x
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-zinc-600">—</span>
                  )}
                </td>
                <td className="p-3 text-center">
                  {bet ? (
                    bet.result === "win" ? (
                      <span
                        className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-2 py-1 text-xs font-bold uppercase"
                        data-testid={`bet-result-${r.favourite_rank}`}
                      >
                        Lay Won +£{Number(bet.pnl || 0).toFixed(2)}
                      </span>
                    ) : bet.result === "loss" ? (
                      <span
                        className="bg-red-500/10 border border-red-500/30 text-red-400 px-2 py-1 text-xs font-bold uppercase"
                        data-testid={`bet-result-${r.favourite_rank}`}
                      >
                        Lay Lost £{Number(bet.pnl || 0).toFixed(2)}
                      </span>
                    ) : (
                      <span
                        className="bg-zinc-700/20 border border-zinc-600/40 text-zinc-400 px-2 py-1 text-xs font-bold uppercase animate-pulse"
                        data-testid={`bet-result-${r.favourite_rank}`}
                      >
                        Awaiting result
                      </span>
                    )
                  ) : (
                    <span className="text-zinc-600">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
