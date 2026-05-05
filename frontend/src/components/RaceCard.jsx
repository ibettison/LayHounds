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

  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="race-card">
      <div className="flex items-center justify-between bg-[#0A0A0A] border-b border-[#2A2A2A] p-4">
        <div>
          <div className="label-xs">Race #{race.race_num}</div>
          <div className="font-display text-2xl uppercase tracking-tight">{race.venue}</div>
        </div>
        <div className="text-right">
          <div className="label-xs">P&amp;L Change</div>
          <div
            className={`font-mono text-2xl font-bold ${
              race.pnl_change >= 0 ? "text-emerald-400" : "text-red-400"
            }`}
            data-testid="race-pnl-change"
          >
            {race.pnl_change >= 0 ? "+" : ""}£{race.pnl_change.toFixed(2)}
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
                <td className="p-3 text-right font-mono text-base">{r.odds.toFixed(2)}</td>
                <td className="p-3 text-right font-mono text-sm">
                  {bet ? (
                    <div>
                      <div className="text-pink-400">£{bet.stake.toFixed(2)}</div>
                      <div className="text-amber-400/80 text-xs">
                        liab £{bet.liability.toFixed(2)}
                      </div>
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
                        Lay Won +£{bet.pnl.toFixed(2)}
                      </span>
                    ) : (
                      <span
                        className="bg-red-500/10 border border-red-500/30 text-red-400 px-2 py-1 text-xs font-bold uppercase"
                        data-testid={`bet-result-${r.favourite_rank}`}
                      >
                        Lay Lost £{bet.pnl.toFixed(2)}
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
