import React, { useEffect, useRef, useState } from "react";
import { Timer, Wifi, Zap, ZapOff } from "lucide-react";
import { api } from "../lib/api";

const TRIGGER_AT_SECS = 60;       // T-60s
const POLL_RACES_MS = 30_000;     // refresh upcoming markets every 30s
const TICK_MS = 1_000;            // countdown tick

/**
 * LiveCountdown — for live sessions only.
 *
 *   • Polls /api/betfair/races every 30s and locks onto the soonest upcoming UK greyhound market.
 *   • Renders a MM:SS countdown to that market's official start time.
 *   • If `autoPlace` is true, fires `onAutoFire(marketId)` exactly once per market
 *     when the countdown drops to TRIGGER_AT_SECS (60s).
 */
export const LiveCountdown = ({ session, autoPlace, onAutoFire }) => {
  const [nextMarket, setNextMarket] = useState(null); // { market_id, venue, market_start_time }
  const [error, setError] = useState(null);
  const [secsToStart, setSecsToStart] = useState(null);
  const firedRef = useRef(new Set()); // remember which markets have already triggered

  // Poll upcoming markets
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await api.betfairRaces(60);
        if (cancelled) return;
        const upcoming = (data.markets || [])
          .map((m) => ({ ...m, startMs: new Date(m.marketStartTime || m.market_start_time).getTime() }))
          .filter((m) => !isNaN(m.startMs) && m.startMs > Date.now() - 1000)
          .sort((a, b) => a.startMs - b.startMs);
        setNextMarket(upcoming[0] || null);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e.response?.data?.detail || e.message || "Betfair unavailable");
        setNextMarket(null);
      }
    };
    load();
    const id = setInterval(load, POLL_RACES_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // Tick the countdown + trigger autoFire
  useEffect(() => {
    if (!nextMarket) { setSecsToStart(null); return; }
    const tick = () => {
      const remaining = Math.floor((nextMarket.startMs - Date.now()) / 1000);
      setSecsToStart(remaining);
      // T-60 hit AND autoPlace ON AND not fired for this market yet → fire
      if (
        autoPlace &&
        remaining <= TRIGGER_AT_SECS &&
        remaining > -5 && // grace window
        !firedRef.current.has(nextMarket.market_id)
      ) {
        firedRef.current.add(nextMarket.market_id);
        onAutoFire?.(nextMarket);
      }
    };
    tick();
    const id = setInterval(tick, TICK_MS);
    return () => clearInterval(id);
  }, [nextMarket, autoPlace, onAutoFire]);

  if (session?.config?.mode !== "live") return null;

  const fmt = (s) => {
    if (s == null) return "—:—";
    const sign = s < 0 ? "-" : "";
    const abs = Math.abs(s);
    const m = Math.floor(abs / 60);
    const sec = abs % 60;
    return `${sign}${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  };

  const urgent = secsToStart != null && secsToStart <= TRIGGER_AT_SECS && secsToStart > 0;
  const past = secsToStart != null && secsToStart <= 0;
  const tone = error
    ? "border-red-500/40 bg-red-500/5"
    : urgent
      ? "border-pink-500/60 bg-pink-500/10 animate-pulse"
      : past
        ? "border-zinc-700 bg-[#1A1A1A]"
        : "border-[#2A2A2A] bg-[#141414]";

  return (
    <div
      data-testid="live-countdown"
      className={`flex items-center gap-3 px-4 py-3 border ${tone} transition-colors`}
    >
      <div className={`w-9 h-9 grid place-items-center ${urgent ? "bg-pink-500/20 text-pink-300" : "bg-[#0A0A0A] text-zinc-400"}`}>
        {error ? <ZapOff className="w-4 h-4 text-red-400" /> : urgent ? <Zap className="w-4 h-4" /> : <Timer className="w-4 h-4" />}
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 flex items-center gap-1.5">
          <Wifi className="w-3 h-3" /> Next Betfair Race
          {autoPlace && (
            <span className="text-pink-400 font-bold ml-1.5" data-testid="auto-place-on-indicator">
              · AUTO-PLACE ON
            </span>
          )}
        </div>
        {error ? (
          <div className="text-xs text-red-400 mt-1 truncate">{error}</div>
        ) : nextMarket ? (
          <div className="flex items-baseline gap-2 mt-0.5">
            <span className="font-display font-bold text-white text-base truncate">
              {nextMarket.venue || "—"} · Race
            </span>
            <span className="text-[10px] font-mono text-zinc-500 uppercase">
              {new Date(nextMarket.startMs).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        ) : (
          <div className="text-xs text-zinc-500 mt-1">No upcoming UK greyhound markets in the next 60 min.</div>
        )}
      </div>

      <div className="text-right">
        <div
          data-testid="countdown-value"
          className={`font-mono font-bold text-2xl tabular-nums leading-none ${
            error ? "text-red-400" : urgent ? "text-pink-300" : past ? "text-zinc-500" : "text-white"
          }`}
        >
          {fmt(secsToStart)}
        </div>
        <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-600 mt-1">
          {past ? "in-play" : "to off"}
        </div>
      </div>
    </div>
  );
};
