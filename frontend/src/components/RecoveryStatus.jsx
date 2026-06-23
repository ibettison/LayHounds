import React from "react";
import { ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";

const money = (value) => `£${Number(value || 0).toFixed(2)}`;

const LevelDots = ({ level, busted, max = 5 }) => (
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

export const RecoveryStatus = ({ chains, maxRecoveryLevel = 5 }) => {
  const ranks = Object.keys(chains).sort((a, b) => parseInt(a) - parseInt(b));

  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="recovery-status-panel">
      <div className="bg-[#0A0A0A] border-b border-[#2A2A2A] p-4">
        <div className="label-xs">Recovery Chains</div>
        <div className="font-display text-xl uppercase tracking-tight">Per-Favourite Status</div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] table-fixed">
          <colgroup>
            <col className="w-[74px]" />
            <col className="w-[74px]" />
            <col className="w-[96px]" />
            <col className="w-[96px]" />
            <col className="w-[96px]" />
            <col className="w-[136px]" />
            <col />
          </colgroup>
          <thead>
            <tr className="bg-[#1C1C1C] text-xs uppercase tracking-wider text-zinc-400">
              <th className="p-3 text-left">Fav</th>
              <th className="p-3 text-left">Level</th>
              <th className="p-3 text-right">Next Stake</th>
              <th className="p-3 text-right">Debt</th>
              <th className="p-3 text-right">Recovery</th>
              <th className="p-3 text-right">Liability</th>
              <th className="p-3 text-center">Recovery Status</th>
            </tr>
          </thead>
          <tbody>
            {ranks.map((rank) => {
              const c = chains[rank];
              const debt = Number(c.outstanding_debt ?? c.accumulated_loss ?? 0);
              const recoveryPct = Number(c.recovery_percentage ?? 1);
              const currentLiability = Number(c.current_liability ?? 0);
              const maxLiability = Number(c.max_liability_allowed ?? 0);
              const status = c.busted
                ? { icon: ShieldX, color: "text-red-400", label: "Busted" }
                : debt <= 0
                ? { icon: ShieldCheck, color: "text-emerald-400", label: "Clean" }
                : { icon: ShieldAlert, color: "text-amber-400", label: c.recovery_state || `L${c.level}` };
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
                    {c.busted ? "—" : money(c.pending_stake)}
                  </td>
                  <td className="p-3 text-right font-mono text-amber-400/80">
                    {money(debt)}
                  </td>
                  <td className="p-3 text-right font-mono text-amber-400/80">
                    {(recoveryPct * 100).toFixed(0)}%
                  </td>
                  <td className="p-3 text-right font-mono text-zinc-300">
                    {maxLiability > 0 ? `${money(currentLiability)} / ${money(maxLiability)}` : "off"}
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
    </div>
  );
};
