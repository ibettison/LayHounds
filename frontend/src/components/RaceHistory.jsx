import React from "react";

const formatRaceTime = (race) => {
  if (race?.market_time_label) return race.market_time_label;
  const isHistorical = String(race?.market_id || "").startsWith("historical:");
  const raw = race?.market_start_time || (isHistorical ? null : race?.timestamp);
  if (!raw) return null;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
};

export const RaceHistory = ({ races }) => {
  const uniqueRaces = [];
  const seen = new Set();
  for (const race of races || []) {
    const key = race.source === "live" && race.market_id ? `live:${race.market_id}` : `race:${race.race_id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    uniqueRaces.push(race);
  }

  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="race-history-panel">
      <div className="bg-[#0A0A0A] border-b border-[#2A2A2A] p-4">
        <div className="label-xs">Day&apos;s Card</div>
        <div className="font-display text-xl uppercase tracking-tight">
          Race History ({uniqueRaces.length})
        </div>
      </div>
      <div className="max-h-[420px] overflow-y-auto">
        {uniqueRaces.length === 0 && (
          <div className="p-6 text-center text-zinc-500 text-sm">No races run yet.</div>
        )}
        {[...uniqueRaces].reverse().map((race) => {
          const winner = race.runners.find((r) => r.trap === race.winning_trap);
          const raceTime = formatRaceTime(race);
          const liveSettled = race.source === "live" && (race.bets || []).some(
            (bet) => bet.result || bet.settled_at || bet.placement_status === "settled" || bet.pnl != null
          );
          const livePending = race.source === "live" && !liveSettled;
          const skippedBets = race.skipped_bets || [];
          const hasBets = (race.bets || []).length > 0;
          return (
            <div
              key={race.race_id}
              data-testid={`history-race-${race.race_num}`}
              className="border-b border-[#2A2A2A] p-3 hover:bg-[#1C1C1C]/50 transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="label-xs">R{race.race_num}</span>
                  {raceTime && (
                    <span className="text-xs text-zinc-500 font-display uppercase">{raceTime}</span>
                  )}
                  <span className="text-xs text-zinc-400 font-display uppercase">{race.venue}</span>
                  {race.category && (
                    <span className="text-[9px] font-mono font-bold uppercase tracking-wider text-pink-300/80">
                      {race.category.grade} · {race.category.distance_m}m
                    </span>
                  )}
                </div>
                <div
                  className={`font-mono font-bold ${
                    race.pnl_change >= 0 ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {race.pnl_change >= 0 ? "+" : ""}£{race.pnl_change.toFixed(2)}
                </div>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className={`trap-${winner?.trap || "-"} w-5 h-5 flex items-center justify-center font-mono text-xs font-bold`}>
                  {winner?.trap ?? "—"}
                </span>
                <span className="text-white truncate flex-1">
                  {winner?.name || (livePending ? "Awaiting Betfair settlement" : "Settled")}
                </span>
                {winner ? (
                  <span className="text-zinc-500 font-mono text-xs">@{Number(winner.odds || 0).toFixed(2)}</span>
                ) : (
                  <span className="text-zinc-600 font-mono text-xs">Betfair P&L</span>
                )}
              </div>
              {race.source === "live" && race.bets?.length > 0 && (
                <div className="mt-2 space-y-1">
                  {race.bets.map((bet) => (
                    <div
                      key={bet.betfair_bet_id || `${race.race_id}-${bet.favourite_rank}`}
                      className="bg-[#0A0A0A] border border-[#2A2A2A] px-2 py-1.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-[10px] font-mono text-zinc-400 truncate">
                            Fav #{bet.favourite_rank} · T{bet.dog_trap} {bet.dog_name}
                          </div>
                          <div className="text-[9px] font-mono text-zinc-600 truncate">
                            {bet.betfair_bet_id ? `Betfair ${bet.betfair_bet_id}` : "Betfair id pending"}
                          </div>
                          {bet.chase_attempts > 1 && (
                            <div className="text-[9px] font-mono text-amber-300/80 truncate">
                              chased {bet.chase_attempts}x{bet.chase_final_price ? ` · final @${Number(bet.chase_final_price).toFixed(2)}` : ""}
                            </div>
                          )}
                        </div>
                        <div className="text-right shrink-0">
                          <div className={`text-[10px] font-mono font-bold uppercase ${
                            bet.result === "win" ? "text-emerald-400"
                              : bet.result === "loss" ? "text-red-400"
                                : "text-amber-400"
                          }`}>
                            {bet.result
                              ? `${bet.result === "win" ? "Lay won" : "Lay lost"} ${bet.pnl >= 0 ? "+" : ""}£${Number(bet.pnl || 0).toFixed(2)}`
                              : (bet.placement_status || "placed")}
                          </div>
                          <div className="text-[9px] font-mono text-zinc-500">
                            £{Number(bet.matched_size ?? bet.stake ?? 0).toFixed(2)}
                            {" "}@{Number(bet.matched_price ?? bet.odds ?? 0).toFixed(2)}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {skippedBets.length > 0 && (
                <div className="mt-2 bg-amber-500/10 border border-amber-500/30 px-2 py-1.5">
                  <div className="text-[9px] font-mono font-bold uppercase tracking-wider text-amber-300">
                    {hasBets ? "Favourite Risk Guard avoided first favourite" : "Favourite Risk Guard skipped"}
                  </div>
                  <div className="text-[10px] text-amber-100/75 mt-0.5">
                    {skippedBets.join(" · ")}
                  </div>
                </div>
              )}
              <div className="text-xs text-zinc-500 mt-1 font-mono">
                Bank: £{race.bank_after.toFixed(2)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
