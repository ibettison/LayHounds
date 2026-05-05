import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { TrendingUp, TrendingDown, Loader2, Shield } from "lucide-react";

export const CapPreview = ({ stake, maxLiabilityCap, numFavourites, commissionRate, oddsMin, oddsMax }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(() => {
      api.previewCap({
        stake: parseFloat(stake),
        max_liability_cap: parseFloat(maxLiabilityCap) || 0,
        num_favourites: parseInt(numFavourites) || 2,
        commission_rate: parseFloat(commissionRate) || 0,
        odds_min: parseFloat(oddsMin) || 1.01,
        odds_max: parseFloat(oddsMax) || 1000,
        iterations: 1500,
      })
        .then((d) => { if (!cancelled) setData(d); })
        .catch(() => { if (!cancelled) setData(null); })
        .finally(() => { if (!cancelled) setLoading(false); });
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [stake, maxLiabilityCap, numFavourites, commissionRate, oddsMin, oddsMax]);

  if (!data && !loading) return null;

  const ev = data?.expected_profit_per_race ?? 0;
  const evPositive = ev > 0;
  const ev100 = ev * 100;

  return (
    <div
      data-testid="cap-preview-panel"
      className="bg-[#0A0A0A] border border-[#2A2A2A] p-3 space-y-2"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-3.5 h-3.5 text-pink-400" />
          <div className="label-xs">Projected Cap Impact (Monte-Carlo ×1500)</div>
        </div>
        {loading && <Loader2 className="w-3.5 h-3.5 animate-spin text-zinc-500" />}
      </div>

      {data && (
        <>
          <div className="grid grid-cols-3 gap-2 text-xs font-mono">
            <div className="p-2 bg-[#141414]">
              <div className="label-xs">Win Rate</div>
              <div className="text-emerald-400 font-bold text-base">{data.win_rate}%</div>
            </div>
            <div className="p-2 bg-[#141414]">
              <div className="label-xs">Bust Rate</div>
              <div className="text-red-400 font-bold text-base">{data.bust_rate}%</div>
            </div>
            <div className="p-2 bg-[#141414]">
              <div className="label-xs">Reach L3</div>
              <div className="text-amber-400 font-bold text-base">{data.reach_l3_rate}%</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="p-2 bg-[#141414] flex items-center justify-between">
              <div>
                <div className="label-xs">EV / Race</div>
                <div className={`font-bold text-base ${evPositive ? "text-emerald-400" : "text-red-400"}`}>
                  {evPositive ? "+" : ""}£{ev.toFixed(3)}
                </div>
              </div>
              {evPositive ? (
                <TrendingUp className="w-5 h-5 text-emerald-400" />
              ) : (
                <TrendingDown className="w-5 h-5 text-red-400" />
              )}
            </div>
            <div className="p-2 bg-[#141414]">
              <div className="label-xs">Worst Chain</div>
              <div className="text-red-400 font-bold text-base">
                £{data.worst_chain_loss.toFixed(2)}
              </div>
            </div>
          </div>

          <div className="space-y-1">
            <div className="label-xs">Bust Level Distribution</div>
            <div className="flex h-4 bg-[#141414]">
              {["L1", "L2", "L3"].map((lvl) => {
                const v = data.bust_distribution[lvl];
                const pct = (v / data.iterations) * 100;
                const color = { L1: "#F59E0B", L2: "#EF4444", L3: "#7F1D1D" }[lvl];
                return pct > 0 ? (
                  <div
                    key={lvl}
                    style={{ width: `${pct}%`, background: color }}
                    title={`${lvl} busts: ${v} (${pct.toFixed(1)}%)`}
                  />
                ) : null;
              })}
            </div>
            <div className="flex gap-3 text-[10px] text-zinc-500 font-mono">
              <span>L1: {data.bust_distribution.L1}</span>
              <span>L2: {data.bust_distribution.L2}</span>
              <span>L3: {data.bust_distribution.L3}</span>
              {data.bust_distribution.L0_cap_blocked > 0 && (
                <span className="text-amber-400">
                  Cap-blocked: {data.bust_distribution.L0_cap_blocked}
                </span>
              )}
            </div>
          </div>

          <div className={`text-[11px] font-mono p-2 border ${
            evPositive
              ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/5"
              : "text-amber-400 border-amber-500/30 bg-amber-500/5"
          }`}>
            {evPositive
              ? `Positive expectancy. Over 100 races with ${numFavourites} favs you'd net ~£${(ev100).toFixed(2)}.`
              : `Negative expectancy. Over 100 races you'd lose ~£${Math.abs(ev100).toFixed(2)}. Increase cap or reduce stake.`}
          </div>
        </>
      )}
    </div>
  );
};
