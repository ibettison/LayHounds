import React from "react";
import { ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";

const LevelDots = ({ level, busted, max = 3 }) => (
  <div className="flex gap-1" data-testid={`level-dots-${level}-${busted}`}>
    {Array.from({ length: max }, (_, idx) => {
      const i = idx + 1;
      const active = i <= level;
      const cls = busted
        ? "bg-red-500"
        : active
        ? "bg-amber-400"
        : "bg-[#2A2A2A]";
      return <span key={i} className={`w-3 h-3 ${cls}`} />;
    })}
  </div>
);

export const RecoveryStatus = ({ chains, maxRecoveryLevel = 3 }) => {
  const ranks = Object.keys(chains).sort((a, b) => parseInt(a) - parseInt(b));

  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="recovery-status-panel">
      <div className="bg-[#0A0A0A] border-b border-[#2A2A2A] p-4">
        <div className="label-xs">Recovery Chains</div>
        <div className="font-display text-xl uppercase tracking-tight">Per-Favourite Status</div>
      </div>
      <table className="w-full table-fixed">
        <colgroup>
          <col className="w-[74px]" />
          <col className="w-[74px]" />
          <col className="w-[96px]" />
          <col className="w-[96px]" />
          <col />
        </colgroup>
        <thead>
          <tr className="bg-[#1C1C1C] text-xs uppercase tracking-wider text-zinc-400">
            <th className="p-3 text-left">Fav</th>
            <th className="p-3 text-left">Level</th>
            <th className="p-3 text-right">Next Stake</th>
            <th className="p-3 text-right">Accum Loss</th>
            <th className="p-3 text-center">Status</th>
          </tr>
        </thead>
        <tbody>
          {ranks.map((rank) => {
            const c = chains[rank];
            const status = c.busted
              ? { icon: ShieldX, color: "text-red-400", label: "Busted" }
              : c.level === 0
              ? { icon: ShieldCheck, color: "text-emerald-400", label: "Clean" }
              : { icon: ShieldAlert, color: "text-amber-400", label: `Recovery L${c.level}` };
            const Icon = status.icon;
            return (
              <tr key={rank} className="border-b border-[#2A2A2A]" data-testid={`recovery-row-${rank}`}>
                <td className="p-3 whitespace-nowrap">
                  <span className="inline-flex whitespace-nowrap bg-pink-500/10 border border-pink-500/30 text-pink-400 px-2 py-0.5 text-xs font-bold uppercase tracking-wider">
                    Fav #{rank}
                  </span>
                </td>
                <td className="p-3">
                  <LevelDots level={c.level} busted={c.busted} max={maxRecoveryLevel} />
                </td>
                <td className="p-3 text-right font-mono">
                  {c.busted ? "—" : `£${c.pending_stake.toFixed(2)}`}
                </td>
                <td className="p-3 text-right font-mono text-amber-400/80">
                  £{c.accumulated_loss.toFixed(2)}
                </td>
                <td className="p-3 text-center">
                  <span className={`inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider ${status.color}`}>
                    <Icon className="w-3.5 h-3.5" />
                    {status.label}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
