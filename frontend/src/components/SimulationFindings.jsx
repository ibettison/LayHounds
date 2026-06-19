import React, { useEffect, useMemo, useState } from "react";
import { BarChart3 } from "lucide-react";
import { api } from "../lib/api";

const fmtMoney = (value) => {
  const n = Number(value || 0);
  return `${n >= 0 ? "+" : "-"}£${Math.abs(n).toFixed(2)}`;
};

const fmtDate = (value) => {
  if (!value) return "Not selected";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 10);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
};

const fmtTime = (value) => {
  if (!value) return "--:--";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).slice(11, 16) || "--:--";
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
};

const replayDayKey = (race) => (race?.race_time || race?.market_start_time || "").slice(0, 10);

export const SimulationFindings = ({ session }) => {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api.historicalReplaySummary()
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.response?.data?.detail || err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const evidence = useMemo(() => {
    const races = (session?.races || []).filter((race) => race.source === "simulator" || race.race_time);
    const byDay = new Map();
    for (const race of races) {
      const day = replayDayKey(race) || "unknown";
      const current = byDay.get(day) || { date: day, races: 0, pnl: 0 };
      current.races += 1;
      current.pnl = Number((current.pnl + Number(race.pnl_change || 0)).toFixed(4));
      byDay.set(day, current);
    }
    const days = [...byDay.values()].sort((a, b) => a.date.localeCompare(b.date));
    const bestDay = days.length ? [...days].sort((a, b) => b.pnl - a.pnl)[0] : null;
    const worstDay = days.length ? [...days].sort((a, b) => a.pnl - b.pnl)[0] : null;
    const lastRace = races[races.length - 1] || null;
    const currentDay = replayDayKey(lastRace) || session?.historical_replay_day || null;
    return {
      races,
      days,
      bestDay,
      worstDay,
      lastRace,
      currentDay,
      pnl: Number(session?.total_pnl || 0),
    };
  }, [session]);

  const packLabel = summary?.source === "bundled_replay_pack"
    ? "Bundled replay pack"
    : summary?.source === "archive"
      ? "Full archive"
      : "Historical data";
  const firstDay = summary?.first_day;
  const lastDay = summary?.last_day;

  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="historical-replay-evidence">
      <div className="flex items-center justify-between gap-3 bg-[#0A0A0A] border-b border-[#2A2A2A] p-4">
        <div>
          <div className="label-xs">Historical Replay Evidence</div>
          <div className="font-display text-2xl uppercase tracking-tight">
            Real Betfair race-card replay
          </div>
        </div>
        <div className="w-10 h-10 bg-pink-600/15 border border-pink-500/30 grid place-items-center">
          <BarChart3 className="w-5 h-5 text-pink-300" />
        </div>
      </div>

      <div className="p-4 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <FindingStat label="Historical days" value={summary?.day_count ?? "--"} sub={packLabel} />
          <FindingStat label="Historical races" value={summary?.race_count?.toLocaleString("en-GB") ?? "--"} sub="UK/IE markets" />
          <FindingStat label="Current replay day" value={fmtDate(evidence.currentDay)} sub={`${evidence.races.length} races completed`} />
          <FindingStat label="Session P&L" value={fmtMoney(evidence.pnl)} sub="current replay session" tone={evidence.pnl >= 0 ? "emerald" : "red"} />
        </div>

        <div className="grid md:grid-cols-3 gap-3 text-sm">
          <Note title="Replay source">
            {error
              ? `Could not load replay metadata: ${error}`
              : summary?.available
                ? `${packLabel} with ${summary.race_count.toLocaleString("en-GB")} historical races across ${summary.day_count} day${summary.day_count === 1 ? "" : "s"}.`
                : "Historical replay metadata is not available yet."}
          </Note>
          <Note title="Date range">
            {firstDay && lastDay
              ? `${fmtDate(firstDay.date)} ${fmtTime(firstDay.first_race_time)} to ${fmtDate(lastDay.date)} ${fmtTime(lastDay.last_race_time)}.`
              : "Waiting for historical replay data."}
          </Note>
          <Note title="Replay progress">
            {evidence.lastRace
              ? `Latest race: ${evidence.lastRace.venue} at ${evidence.lastRace.market_time_label || fmtTime(evidence.lastRace.race_time)}.`
              : "Run the first historical race to start building session evidence."}
          </Note>
        </div>

        <ResultTable
          rows={[
            { label: "Replay days completed", value: evidence.days.length || 0, note: "days with at least one race run" },
            { label: "Best replay day so far", value: evidence.bestDay ? fmtMoney(evidence.bestDay.pnl) : "--", note: evidence.bestDay ? fmtDate(evidence.bestDay.date) : "not enough races yet" },
            { label: "Worst replay day so far", value: evidence.worstDay ? fmtMoney(evidence.worstDay.pnl) : "--", note: evidence.worstDay ? fmtDate(evidence.worstDay.date) : "not enough races yet" },
            { label: "Races completed today", value: evidence.currentDay ? (evidence.days.find((day) => day.date === evidence.currentDay)?.races || 0) : 0, note: "current historical card" },
          ]}
        />

        <div className="text-xs text-zinc-500 leading-relaxed">
          This panel describes the historical replay data and the current replay session. It is not a live Betfair forecast, and past historical results do not guarantee future live results.
        </div>
      </div>
    </div>
  );
};

const ResultTable = ({ rows }) => (
  <div>
    <div className="label-xs mb-2">Current replay evidence</div>
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px]">
        <thead>
          <tr className="text-xs uppercase tracking-wider text-zinc-500 border-b border-[#2A2A2A]">
            <th className="py-2 text-left">Metric</th>
            <th className="py-2 text-right">Value</th>
            <th className="py-2 text-right">Context</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-[#2A2A2A]/70">
              <td className="py-3 pr-3 text-sm text-white font-bold">{row.label}</td>
              <td className="py-3 pr-3 text-right text-emerald-400 font-mono">{row.value}</td>
              <td className="py-3 text-right text-zinc-400 text-sm">{row.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

const FindingStat = ({ label, value, sub, tone = "white" }) => (
  <div className="bg-[#0A0A0A] border border-[#2A2A2A] p-3">
    <div className="label-xs mb-1">{label}</div>
    <div className={`font-mono text-xl font-bold ${
      tone === "emerald" ? "text-emerald-400" : tone === "red" ? "text-red-400" : "text-white"
    }`}>
      {value}
    </div>
    <div className="text-xs text-zinc-500 font-mono">{sub}</div>
  </div>
);

const Note = ({ title, children }) => (
  <div className="bg-[#0A0A0A] border border-[#2A2A2A] p-3">
    <div className="font-display uppercase tracking-tight text-lg mb-1">{title}</div>
    <div className="text-zinc-400 leading-relaxed">{children}</div>
  </div>
);
