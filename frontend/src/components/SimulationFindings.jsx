import React, { useEffect, useMemo, useState } from "react";
import { BarChart3, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";
import { api } from "../lib/api";

const fmtSignedMoney = (value) => {
  const n = Number(value || 0);
  return `${n >= 0 ? "+" : "-"}£${Math.abs(n).toFixed(2)}`;
};

const fmtMoney = (value) => `£${Math.abs(Number(value || 0)).toFixed(2)}`;

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
const isReplaySession = (session) => (session?.config?.mode || "simulator") === "simulator";
const isElasticSession = (session) => session?.config?.recovery_mode === "elastic";
const recoveryDebt = (chain) => Number(chain?.outstanding_debt ?? chain?.accumulated_loss ?? 0) || 0;

const combineSessions = (sessions, current) => {
  const byId = new Map();
  for (const session of sessions || []) {
    if (session?.id) byId.set(session.id, session);
  }
  if (current?.id) byId.set(current.id, current);
  return [...byId.values()];
};

const bestBy = (items, selector) => {
  if (!items.length) return null;
  return items.reduce((best, item) => (selector(item) > selector(best) ? item : best), items[0]);
};

const worstBy = (items, selector) => {
  if (!items.length) return null;
  return items.reduce((worst, item) => (selector(item) < selector(worst) ? item : worst), items[0]);
};

export const SimulationFindings = ({ session, sessions = [] }) => {
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
    const allSessions = combineSessions(sessions, session);
    const replaySessions = allSessions.filter(isReplaySession);
    const elasticSessions = replaySessions.filter(isElasticSession);
    const replayRaces = replaySessions.flatMap((item) =>
      (item.races || []).map((race) => ({ ...race, session: item })),
    );
    const elasticRaces = elasticSessions.flatMap((item) =>
      (item.races || []).map((race) => ({ ...race, session: item })),
    );
    const elasticBets = elasticRaces.flatMap((race) =>
      (race.bets || []).map((bet) => ({ ...bet, race, session: race.session })),
    );
    const recoveryBets = elasticBets.filter((bet) =>
      Number(bet.recovery_level || 0) > 0 || Number(bet.outstanding_debt_before || 0) > 0,
    );
    const settledRecoveryBets = recoveryBets.filter((bet) => bet.result);
    const recoveredBets = settledRecoveryBets.map((bet) => {
      const before = Number(bet.outstanding_debt_before || 0);
      const after = Number(bet.outstanding_debt_after ?? before);
      const debtCleared = Math.max(before - after, 0);
      return {
        ...bet,
        debtCleared,
        pnlValue: Number(bet.pnl || 0),
      };
    });
    const cappedElasticBets = recoveryBets.filter((bet) => Number(bet.recovery_percentage_used ?? 1) < 1);

    const currentRaces = (session?.races || []).filter((race) => race.source === "simulator" || race.race_time);
    const byDay = new Map();
    for (const race of currentRaces) {
      const day = replayDayKey(race) || "unknown";
      const current = byDay.get(day) || { date: day, races: 0, pnl: 0 };
      current.races += 1;
      current.pnl = Number((current.pnl + Number(race.pnl_change || 0)).toFixed(4));
      byDay.set(day, current);
    }

    const days = [...byDay.values()].sort((a, b) => a.date.localeCompare(b.date));
    const lastRace = currentRaces[currentRaces.length - 1] || null;
    const totalPnl = replaySessions.reduce((sum, item) => sum + Number(item.total_pnl || 0), 0);
    const positiveSessions = replaySessions.filter((item) => Number(item.total_pnl || 0) > 0).length;
    const negativeSessions = replaySessions.filter((item) => Number(item.total_pnl || 0) < 0).length;
    const losingRaces = replayRaces.filter((race) => Number(race.pnl_change || 0) < 0);
    const worstRace = worstBy(losingRaces, (race) => Number(race.pnl_change || 0));
    const biggestLiability = bestBy(
      replayRaces.flatMap((race) => (race.bets || []).map((bet) => ({ ...bet, race, session: race.session }))),
      (bet) => Number(bet.liability || 0),
    );
    const bestRecovery = bestBy(recoveredBets, (bet) => bet.debtCleared || bet.pnlValue);
    const deepestElasticDebt = bestBy(recoveryBets, (bet) => Number(bet.outstanding_debt_before || 0));
    const currentDebt = Object.values(session?.recovery_chains || {}).reduce((sum, chain) => sum + recoveryDebt(chain), 0);
    const skippedMarkets = replayRaces.reduce((sum, race) => sum + (race.skipped_audit?.length || race.skipped_bets?.length || 0), 0);
    const currentDay = replayDayKey(lastRace) || session?.historical_replay_day || null;

    return {
      replaySessions,
      elasticSessions,
      replayRaces,
      currentRaces,
      days,
      bestDay: bestBy(days, (day) => day.pnl),
      worstDay: worstBy(days, (day) => day.pnl),
      bestSession: bestBy(replaySessions, (item) => Number(item.total_pnl || 0)),
      worstSession: worstBy(replaySessions, (item) => Number(item.total_pnl || 0)),
      lastRace,
      currentDay,
      currentPnl: Number(session?.total_pnl || 0),
      totalPnl,
      positiveSessions,
      negativeSessions,
      worstRace,
      biggestLiability,
      bestRecovery,
      deepestElasticDebt,
      recoveryBets,
      cappedElasticBets,
      currentDebt,
      skippedMarkets,
    };
  }, [session, sessions]);

  const packLabel = summary?.source === "bundled_replay_pack"
    ? "Bundled replay pack"
    : summary?.source === "archive"
      ? "Full archive"
      : "Historical data";
  const firstDay = summary?.first_day;
  const lastDay = summary?.last_day;
  const winRate = evidence.replaySessions.length
    ? `${Math.round((evidence.positiveSessions / evidence.replaySessions.length) * 100)}%`
    : "--";

  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="historical-replay-evidence">
      <div className="flex items-center justify-between gap-3 bg-[#0A0A0A] border-b border-[#2A2A2A] p-4">
        <div>
          <div className="label-xs">Historical Replay Evidence</div>
          <div className="font-display text-2xl uppercase tracking-tight">
            Session evidence and Elastic recovery record
          </div>
        </div>
        <div className="w-10 h-10 bg-pink-600/15 border border-pink-500/30 grid place-items-center">
          <BarChart3 className="w-5 h-5 text-pink-300" />
        </div>
      </div>

      <div className="p-4 space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <FindingStat label="Replay sessions" value={evidence.replaySessions.length} sub={`${evidence.elasticSessions.length} Elastic`} />
          <FindingStat label="Replay races" value={evidence.replayRaces.length.toLocaleString("en-GB")} sub={`${summary?.race_count?.toLocaleString("en-GB") ?? "--"} in pack`} />
          <FindingStat label="All replay P&L" value={fmtSignedMoney(evidence.totalPnl)} sub={`${evidence.positiveSessions}W ${evidence.negativeSessions}L - win ${winRate}`} tone={evidence.totalPnl >= 0 ? "emerald" : "red"} />
          <FindingStat label="Current session" value={fmtSignedMoney(evidence.currentPnl)} sub={`${evidence.currentRaces.length} races`} tone={evidence.currentPnl >= 0 ? "emerald" : "red"} />
        </div>

        <div className="grid md:grid-cols-3 gap-3 text-sm">
          <Note title="Replay source" icon={BarChart3}>
            {error
              ? `Could not load replay metadata: ${error}`
              : summary?.available
                ? `${packLabel}: ${summary.race_count.toLocaleString("en-GB")} races across ${summary.day_count} historical day${summary.day_count === 1 ? "" : "s"}.`
                : "Historical replay metadata is not available yet."}
          </Note>
          <Note title="Highest loss" icon={TrendingDown}>
            {evidence.worstRace
              ? `${fmtSignedMoney(evidence.worstRace.pnl_change)} at ${evidence.worstRace.venue} in session ${evidence.worstRace.session.id.slice(0, 8)}.`
              : "Run historical races to record the largest losing race."}
          </Note>
          <Note title="Best Elastic recovery" icon={ShieldCheck}>
            {evidence.bestRecovery
              ? `${fmtMoney(evidence.bestRecovery.debtCleared || evidence.bestRecovery.pnlValue)} recovered on ${evidence.bestRecovery.race.venue}, L${evidence.bestRecovery.recovery_level}, ${evidence.bestRecovery.recovery_state}.`
              : "Elastic recovery bets will appear here after a recovery win."}
          </Note>
        </div>

        <ResultTable
          title="Cross-session replay record"
          rows={[
            { label: "Saved replay sessions", value: evidence.replaySessions.length, note: `${evidence.elasticSessions.length} using Elastic recovery` },
            { label: "Positive replay sessions", value: `${evidence.positiveSessions}/${evidence.replaySessions.length || 0}`, note: `win rate ${winRate}` },
            { label: "Best session P&L", value: evidence.bestSession ? fmtSignedMoney(evidence.bestSession.total_pnl) : "--", note: evidence.bestSession ? `session ${evidence.bestSession.id.slice(0, 8)}` : "no sessions yet", tone: "emerald" },
            { label: "Worst session P&L", value: evidence.worstSession ? fmtSignedMoney(evidence.worstSession.total_pnl) : "--", note: evidence.worstSession ? `session ${evidence.worstSession.id.slice(0, 8)}` : "no sessions yet", tone: "red" },
            { label: "Highest race loss", value: evidence.worstRace ? fmtSignedMoney(evidence.worstRace.pnl_change) : "--", note: evidence.worstRace ? `${evidence.worstRace.venue} - race ${evidence.worstRace.race_num}` : "no races yet", tone: "red" },
            { label: "Largest liability risked", value: evidence.biggestLiability ? fmtMoney(evidence.biggestLiability.liability) : "--", note: evidence.biggestLiability ? `${evidence.biggestLiability.race.venue} - rank ${evidence.biggestLiability.favourite_rank}` : "no bets yet" },
          ]}
        />

        <ResultTable
          title="Elastic recovery evidence"
          rows={[
            { label: "Elastic recovery bets", value: evidence.recoveryBets.length, note: "bets placed with active recovery debt" },
            { label: "Capped or partial recovery", value: evidence.cappedElasticBets.length, note: "Elastic debt-band bets below 100% recovery" },
            { label: "Deepest Elastic debt faced", value: evidence.deepestElasticDebt ? fmtMoney(evidence.deepestElasticDebt.outstanding_debt_before) : "--", note: evidence.deepestElasticDebt ? `${evidence.deepestElasticDebt.recovery_state} - L${evidence.deepestElasticDebt.recovery_level}` : "no recovery debt yet" },
            { label: "Best debt reduction", value: evidence.bestRecovery ? fmtMoney(evidence.bestRecovery.debtCleared || evidence.bestRecovery.pnlValue) : "--", note: evidence.bestRecovery ? `${evidence.bestRecovery.race.venue} - rank ${evidence.bestRecovery.favourite_rank}` : "waiting for recovery win", tone: "emerald" },
            { label: "Current open recovery debt", value: fmtMoney(evidence.currentDebt), note: "active session chains" },
            { label: "Skipped opportunities logged", value: evidence.skippedMarkets, note: "risk guard, cap and odds filters" },
          ]}
        />

        <div className="grid md:grid-cols-3 gap-3 text-sm">
          <Note title="Date range" icon={TrendingUp}>
            {firstDay && lastDay
              ? `${fmtDate(firstDay.date)} ${fmtTime(firstDay.first_race_time)} to ${fmtDate(lastDay.date)} ${fmtTime(lastDay.last_race_time)}.`
              : "Waiting for historical replay data."}
          </Note>
          <Note title="Current replay day" icon={BarChart3}>
            {evidence.currentDay
              ? `${fmtDate(evidence.currentDay)} - ${evidence.currentRaces.length} races completed in this session.`
              : "Run the first historical race to start the current replay record."}
          </Note>
          <Note title="Latest race" icon={ShieldCheck}>
            {evidence.lastRace
              ? `${evidence.lastRace.venue} at ${evidence.lastRace.market_time_label || fmtTime(evidence.lastRace.race_time)}.`
              : "No historical race has been run in this session yet."}
          </Note>
        </div>

        <ResultTable
          title="Current session days"
          rows={[
            { label: "Replay days completed", value: evidence.days.length || 0, note: "days with at least one race run" },
            { label: "Best replay day so far", value: evidence.bestDay ? fmtSignedMoney(evidence.bestDay.pnl) : "--", note: evidence.bestDay ? fmtDate(evidence.bestDay.date) : "not enough races yet", tone: "emerald" },
            { label: "Worst replay day so far", value: evidence.worstDay ? fmtSignedMoney(evidence.worstDay.pnl) : "--", note: evidence.worstDay ? fmtDate(evidence.worstDay.date) : "not enough races yet", tone: "red" },
            { label: "Races completed today", value: evidence.currentDay ? (evidence.days.find((day) => day.date === evidence.currentDay)?.races || 0) : 0, note: "current historical card" },
          ]}
        />

        <div className="text-xs text-zinc-500 leading-relaxed">
          This panel records saved Historical Replay sessions and Elastic recovery behaviour from the races already run. It is evidence from historical Betfair markets, not a guarantee of future live results.
        </div>
      </div>
    </div>
  );
};

const ResultTable = ({ rows, title }) => (
  <div>
    <div className="label-xs mb-2">{title}</div>
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px]">
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
              <td className={`py-3 pr-3 text-right font-mono ${
                row.tone === "emerald" ? "text-emerald-400" : row.tone === "red" ? "text-red-400" : "text-white"
              }`}>
                {row.value}
              </td>
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

const Note = ({ title, children, icon: Icon }) => (
  <div className="bg-[#0A0A0A] border border-[#2A2A2A] p-3">
    <div className="flex items-center gap-2 mb-1">
      {Icon && <Icon className="w-4 h-4 text-pink-300" />}
      <div className="font-display uppercase tracking-tight text-lg">{title}</div>
    </div>
    <div className="text-zinc-400 leading-relaxed">{children}</div>
  </div>
);
