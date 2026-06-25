import React, { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Shield, TrendingUp } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

const BASE_STAKE = 0.05;
const BASE_SMOOTH_TOTAL_PNL = 3.2868;
const BASE_PROFIT_TOTAL_PNL = 7.292;
const HISTORICAL_DAYS = 30;
const SMOOTH_POSITIVE_DAYS = 27;
const PROFIT_POSITIVE_DAYS = 22;
const SMOOTH_STOP_WIN_MULTIPLE = 10;
const SMOOTH_STOP_LOSS_MULTIPLE = 80;
const PROFIT_STOP_WIN_MULTIPLE = 20;
const PROFIT_STOP_LOSS_MULTIPLE = 40;
const LIABILITY_CAP_MULTIPLE = 100;
const STARTER_BANK_MULTIPLE = 800;

const money = (value) => `\u00a3${Number(value || 0).toFixed(2)}`;

const stakeFromWorstDay = (value) => {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return BASE_STAKE;
  return Math.max(0.01, Math.round((n / SMOOTH_STOP_LOSS_MULTIPLE) * 100) / 100);
};

const starterRows = [
  [0.05, 40, 0.5, 4, 5],
  [0.50, 400, 5, 40, 50],
  [1.00, 800, 10, 80, 100],
  [1.50, 1200, 15, 120, 150],
  [2.00, 1600, 20, 160, 200],
];

export const RiskScaledRecommendation = ({ form, update, inputCls }) => {
  const currentBank = Number(form.starting_bank || 0);
  const [mode, setMode] = useState("worst_day");
  const [bankroll, setBankroll] = useState(currentBank || 100);
  const [worstDay, setWorstDay] = useState(10);

  useEffect(() => {
    if (currentBank > 0) {
      setBankroll(currentBank);
    }
  }, [currentBank]);

  const recommendation = useMemo(() => {
    const bank = Number(bankroll || currentBank || 0);
    const acceptedWorstDay = mode === "bankroll" ? Math.max(bank * 0.1, 10) : Number(worstDay || 0);
    const stake = stakeFromWorstDay(acceptedWorstDay);
    const scale = stake / BASE_STAKE;
    const stopWin = Number((stake * SMOOTH_STOP_WIN_MULTIPLE).toFixed(2));
    const stopLoss = Number((stake * SMOOTH_STOP_LOSS_MULTIPLE).toFixed(2));
    const maxLiabilityCap = Number((stake * LIABILITY_CAP_MULTIPLE).toFixed(2));
    const suggestedBank = Number((stake * STARTER_BANK_MULTIPLE).toFixed(2));
    const bankAtRiskPct = bank > 0 ? (stopLoss / bank) * 100 : 0;

    return {
      stake,
      stopWin,
      stopLoss,
      maxLiabilityCap,
      maxRecoveryLevel: 3,
      totalPnl: Number((BASE_SMOOTH_TOTAL_PNL * scale).toFixed(2)),
      profitModePnl: Number((BASE_PROFIT_TOTAL_PNL * scale).toFixed(2)),
      avgDailyPnl: Number(((BASE_SMOOTH_TOTAL_PNL * scale) / HISTORICAL_DAYS).toFixed(2)),
      worstDay: -stopLoss,
      suggestedBank,
      bankAtRiskPct,
      bank,
    };
  }, [bankroll, currentBank, mode, worstDay]);

  const danger = recommendation.bank > 0 && recommendation.bankAtRiskPct >= 25;
  const caution = !danger && recommendation.bank > 0 && recommendation.bankAtRiskPct >= 12;

  const applyRecommendation = () => {
    update("stake", recommendation.stake);
    update("max_recovery_level", recommendation.maxRecoveryLevel);
    update("max_liability_cap", recommendation.maxLiabilityCap);
    update("stop_win", recommendation.stopWin);
    update("stop_loss", recommendation.stopLoss);
    update("favourite_risk_guard", "strict");
    update("num_favourites", 2);
    update("max_races", 200);
  };

  const updateBankroll = (value) => {
    setBankroll(value);
    update("starting_bank", value);
  };

  return (
    <div className="col-span-2 border border-emerald-500/30 bg-emerald-500/5 p-3 space-y-3" data-testid="risk-scaled-recommendation">
      <div>
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-emerald-300" />
          <div className="font-display uppercase text-sm font-bold text-emerald-200">Starter bank guide</div>
        </div>
        <div className="text-[11px] text-zinc-400 mt-1 leading-relaxed">
          Based on the bundled Historical Replay pack: 30 UK/IE race days, 3,644 races.
          The smoother setup finished positive on 27/30 days; the higher-profit setup made more overall P&L with more red days.
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="border border-emerald-500/20 bg-[#0A0A0A] p-2">
          <div className="flex items-center gap-1.5 text-emerald-300 font-display uppercase text-xs font-bold">
            <Shield className="w-3.5 h-3.5" /> Smoother start
          </div>
          <div className="text-zinc-400 mt-1 leading-relaxed">
            Stop-win x{SMOOTH_STOP_WIN_MULTIPLE}, stop-loss x{SMOOTH_STOP_LOSS_MULTIPLE}, cap x{LIABILITY_CAP_MULTIPLE}.
            Used for the starter bank ladder.
          </div>
        </div>
        <div className="border border-pink-500/20 bg-[#0A0A0A] p-2">
          <div className="flex items-center gap-1.5 text-pink-300 font-display uppercase text-xs font-bold">
            <TrendingUp className="w-3.5 h-3.5" /> Higher profit
          </div>
          <div className="text-zinc-400 mt-1 leading-relaxed">
            Stop-win x{PROFIT_STOP_WIN_MULTIPLE}, stop-loss x{PROFIT_STOP_LOSS_MULTIPLE}, cap x{LIABILITY_CAP_MULTIPLE}.
            Stronger P&L, but fewer positive days.
          </div>
        </div>
      </div>

      <div className="bg-[#0A0A0A] border border-[#2A2A2A] overflow-x-auto">
        <table className="w-full text-[10px] font-mono">
          <thead className="text-zinc-500 uppercase">
            <tr>
              <th className="text-left p-2">Stake</th>
              <th className="text-left p-2">Starter bank</th>
              <th className="text-left p-2">Stop win</th>
              <th className="text-left p-2">Stop loss</th>
              <th className="text-left p-2">Cap</th>
            </tr>
          </thead>
          <tbody>
            {starterRows.map(([stake, bank, stopWin, stopLoss, cap]) => (
              <tr key={stake} className="border-t border-[#1F1F1F]">
                <td className="p-2 text-white">{money(stake)}</td>
                <td className="p-2 text-emerald-300">{money(bank)}</td>
                <td className="p-2 text-zinc-300">{money(stopWin)}</td>
                <td className="p-2 text-zinc-300">{money(stopLoss)}</td>
                <td className="p-2 text-zinc-300">{money(cap)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {[
          ["worst_day", "Choose worst day", "Derive stake from accepted daily loss."],
          ["bankroll", "Use bankroll", "Uses 10% of bank as daily loss room."],
        ].map(([id, title, desc]) => (
          <button
            key={id}
            type="button"
            onClick={() => setMode(id)}
            className={`p-2 border text-left transition-colors ${
              mode === id ? "border-emerald-400 bg-emerald-500/10" : "border-[#2A2A2A] hover:bg-[#1C1C1C]"
            }`}
          >
            <div className="label-xs">{title}</div>
            <div className="text-[10px] text-zinc-500">{desc}</div>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label className="label-xs">Bankroll / live bank £</Label>
          <Input data-testid="risk-bankroll-input" type="number" step="0.01" value={bankroll} onChange={(e) => updateBankroll(e.target.value)} className={inputCls} />
        </div>
        <div className="space-y-1">
          <Label className="label-xs">Acceptable worst day £</Label>
          <Input data-testid="risk-worst-day-input" type="number" step="0.01" value={worstDay} onChange={(e) => setWorstDay(e.target.value)} disabled={mode === "bankroll"} className={`${inputCls} disabled:opacity-50`} />
        </div>
      </div>

      <div className="grid grid-cols-5 gap-1.5 text-[10px] font-mono">
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Stake</div><div className="text-white font-bold">{money(recommendation.stake)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">L</div><div className="text-white font-bold">L3</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Cap</div><div className="text-white font-bold">{money(recommendation.maxLiabilityCap)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Stop win</div><div className="text-white font-bold">{money(recommendation.stopWin)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Stop loss</div><div className="text-white font-bold">{money(recommendation.stopLoss)}</div></div>
      </div>

      <div className="grid grid-cols-3 gap-1.5 text-[10px] font-mono">
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Smooth P/L</div><div className="text-emerald-300 font-bold">{money(recommendation.totalPnl)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Profit P/L</div><div className="text-pink-300 font-bold">{money(recommendation.profitModePnl)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Win days</div><div className="text-emerald-300 font-bold">{SMOOTH_POSITIVE_DAYS}/{HISTORICAL_DAYS}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Worst day</div><div className="text-red-300 font-bold">{money(recommendation.worstDay)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Starter bank</div><div className="text-emerald-300 font-bold">{money(recommendation.suggestedBank)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Profit days</div><div className="text-pink-300 font-bold">{PROFIT_POSITIVE_DAYS}/{HISTORICAL_DAYS}</div></div>
      </div>

      {(danger || caution) ? (
        <div className={`flex items-start gap-2 p-2 border text-[11px] leading-relaxed ${danger ? "border-red-500/40 bg-red-500/10 text-red-200" : "border-amber-500/40 bg-amber-500/10 text-amber-200"}`}>
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>{danger ? "Danger" : "Caution"}: selected stop-loss is about {recommendation.bankAtRiskPct.toFixed(1)}% of the bank entered.</div>
        </div>
      ) : recommendation.bank > 0 ? (
        <div className="flex items-center gap-2 text-[11px] text-emerald-200">
          <CheckCircle2 className="w-4 h-4" />
          Selected stop-loss is about {recommendation.bankAtRiskPct.toFixed(1)}% of the bank entered.
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-3">
        <div className="text-[10px] text-zinc-500 font-mono">Replay evidence only; review in Historical Replay before live use. No profit guarantee.</div>
        <Button type="button" data-testid="apply-risk-scaled-config" onClick={applyRecommendation} className="rounded-none bg-emerald-600 hover:bg-emerald-500 text-white font-bold uppercase tracking-wider">
          Apply smoother setup
        </Button>
      </div>
    </div>
  );
};
