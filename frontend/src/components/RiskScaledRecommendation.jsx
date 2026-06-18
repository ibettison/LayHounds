import React, { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Shield } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

const BASE_STAKE = 0.05;
const BASE_TOTAL_PNL = 119.1493;
const BASE_AVG_DAILY_PNL = 0.7401;
const HISTORICAL_DAYS = 161;
const WINNING_DAY_PERCENTAGE = 77.64;
const HISTORICAL_BUSTS = 15;
const STOP_WIN_MULTIPLE = 100;
const STOP_LOSS_MULTIPLE = 200;
const LIABILITY_CAP_MULTIPLE = 200;
const MAX_DRAWDOWN_MULTIPLE = 278.852;

const money = (value) => `\u00a3${Number(value || 0).toFixed(2)}`;

const stakeFromWorstDay = (value) => {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return BASE_STAKE;
  return Math.max(0.01, Math.round((n / STOP_LOSS_MULTIPLE) * 100) / 100);
};

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
    const stopWin = Number((stake * STOP_WIN_MULTIPLE).toFixed(2));
    const stopLoss = Number((stake * STOP_LOSS_MULTIPLE).toFixed(2));
    const maxLiabilityCap = Number((stake * LIABILITY_CAP_MULTIPLE).toFixed(2));
    const maxDailyDrawdown = Number((stake * MAX_DRAWDOWN_MULTIPLE).toFixed(2));
    const bankAtRiskPct = bank > 0 ? (maxDailyDrawdown / bank) * 100 : 0;

    return {
      stake,
      stopWin,
      stopLoss,
      maxLiabilityCap,
      maxRecoveryLevel: 5,
      totalPnl: Number((BASE_TOTAL_PNL * scale).toFixed(2)),
      avgDailyPnl: Number((BASE_AVG_DAILY_PNL * scale).toFixed(2)),
      worstDay: -stopLoss,
      maxDailyDrawdown,
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
  };

  return (
    <div className="col-span-2 border border-emerald-500/30 bg-emerald-500/5 p-3 space-y-3" data-testid="risk-scaled-recommendation">
      <div>
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-emerald-300" />
          <div className="font-display uppercase text-sm font-bold text-emerald-200">Risk-scaled recommendation</div>
        </div>
        <div className="text-[11px] text-zinc-400 mt-1 leading-relaxed">
          Uses the strongest 2026 UK/IE historical scaling pattern: L5 recovery, cap 200x stake,
          stop-win 100x stake, stop-loss 200x stake.
        </div>
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
          <Input data-testid="risk-bankroll-input" type="number" step="0.01" value={bankroll} onChange={(e) => setBankroll(e.target.value)} className={inputCls} />
        </div>
        <div className="space-y-1">
          <Label className="label-xs">Acceptable worst day £</Label>
          <Input data-testid="risk-worst-day-input" type="number" step="0.01" value={worstDay} onChange={(e) => setWorstDay(e.target.value)} disabled={mode === "bankroll"} className={`${inputCls} disabled:opacity-50`} />
        </div>
      </div>

      <div className="grid grid-cols-5 gap-1.5 text-[10px] font-mono">
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Stake</div><div className="text-white font-bold">{money(recommendation.stake)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">L</div><div className="text-white font-bold">L5</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Cap</div><div className="text-white font-bold">{money(recommendation.maxLiabilityCap)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Stop win</div><div className="text-white font-bold">{money(recommendation.stopWin)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Stop loss</div><div className="text-white font-bold">{money(recommendation.stopLoss)}</div></div>
      </div>

      <div className="grid grid-cols-3 gap-1.5 text-[10px] font-mono">
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Hist P/L</div><div className="text-emerald-300 font-bold">{money(recommendation.totalPnl)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Avg/day</div><div className="text-emerald-300 font-bold">{money(recommendation.avgDailyPnl)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Win days</div><div className="text-emerald-300 font-bold">{WINNING_DAY_PERCENTAGE}%</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Worst day</div><div className="text-red-300 font-bold">{money(recommendation.worstDay)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Max DD</div><div className="text-red-300 font-bold">{money(recommendation.maxDailyDrawdown)}</div></div>
        <div className="bg-[#0A0A0A] p-2"><div className="label-xs">Busts</div><div className="text-amber-300 font-bold">{HISTORICAL_BUSTS}/{HISTORICAL_DAYS}</div></div>
      </div>

      {(danger || caution) ? (
        <div className={`flex items-start gap-2 p-2 border text-[11px] leading-relaxed ${danger ? "border-red-500/40 bg-red-500/10 text-red-200" : "border-amber-500/40 bg-amber-500/10 text-amber-200"}`}>
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>{danger ? "Danger" : "Caution"}: historical max daily drawdown is about {recommendation.bankAtRiskPct.toFixed(1)}% of the bank entered.</div>
        </div>
      ) : recommendation.bank > 0 ? (
        <div className="flex items-center gap-2 text-[11px] text-emerald-200">
          <CheckCircle2 className="w-4 h-4" />
          Historical max daily drawdown is about {recommendation.bankAtRiskPct.toFixed(1)}% of the bank entered.
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-3">
        <div className="text-[10px] text-zinc-500 font-mono">Historical replay evidence only; no profit guarantee.</div>
        <Button type="button" data-testid="apply-risk-scaled-config" onClick={applyRecommendation} className="rounded-none bg-emerald-600 hover:bg-emerald-500 text-white font-bold uppercase tracking-wider">
          Apply
        </Button>
      </div>
    </div>
  );
};
