import React from "react";

export const RaceHistory = ({ races }) => {
  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="race-history-panel">
      <div className="bg-[#0A0A0A] border-b border-[#2A2A2A] p-4">
        <div className="label-xs">Day&apos;s Card</div>
        <div className="font-display text-xl uppercase tracking-tight">
          Race History ({races.length})
        </div>
      </div>
      <div className="max-h-[420px] overflow-y-auto">
        {races.length === 0 && (
          <div className="p-6 text-center text-zinc-500 text-sm">No races run yet.</div>
        )}
        {[...races].reverse().map((race) => {
          const winner = race.runners.find((r) => r.trap === race.winning_trap);
          return (
            <div
              key={race.race_id}
              data-testid={`history-race-${race.race_num}`}
              className="border-b border-[#2A2A2A] p-3 hover:bg-[#1C1C1C]/50 transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="label-xs">R{race.race_num}</span>
                  <span className="text-xs text-zinc-400 font-display uppercase">{race.venue}</span>
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
                  {winner?.trap || "N/A"}
                </span>
                <span className="text-white truncate flex-1">{winner?.name || "not found"}</span>
                <span className="text-zinc-500 font-mono text-xs">@{winner?.odds.toFixed(2) || 0}</span>
              </div>
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
