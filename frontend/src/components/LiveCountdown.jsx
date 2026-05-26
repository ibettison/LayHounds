import React, { useEffect, useRef, useState } from "react";
import { Timer, Wifi, Zap, ZapOff } from "lucide-react";
import { api } from "../lib/api";

const TRIGGER_AT_SECS = 60;              // T-60s
const POLL_RACES_MS_FAR = 30_000;        // when next race is > 5 min away
const POLL_RACES_MS_NEAR = 8_000;        // when next race is < 5 min away — refresh faster
const NEAR_WINDOW_SECS = 300;            // 5 min — what we consider "near"
const TICK_MS = 1_000;

/**
 * LiveCountdown — for live sessions only.
 *
 *   • Adaptively polls /api/betfair/races: 30s cadence normally, 8s once we're
 *     within 5 minutes of the next race (so we never miss the hand-off between
 *     race N going in-play and race N+1 becoming the new "next").
 *   • Renders a MM:SS countdown to the locked-on market's official start time.
 *   • If `autoPlace` is true, fires `onAutoFire(market)` exactly once per market
 *     when the countdown drops to TRIGGER_AT_SECS (60s).
 *   • Console-logs every fire / skip decision so the user can audit auto-place
 *     behaviour from the browser devtools.
 */
export const LiveCountdown = ({ session, autoPlace, onAutoFire }) => {
  const [nextMarket, setNextMarket] = useState(null);
  const [error, setError] = useState(null);
  const [secsToStart, setSecsToStart] = useState(null);
  // Map of marketId → epochMs when we fired (so we never re-fire the same race).
  const firedRef = useRef(new Map());
  // Latest values so the tick callback always sees them without depending on them.
  const autoPlaceRef = useRef(autoPlace);
  const onAutoFireRef = useRef(onAutoFire);
  const sessionStatusRef = useRef(session?.status);
  useEffect(() => { autoPlaceRef.current = autoPlace; }, [autoPlace]);
  useEffect(() => { onAutoFireRef.current = onAutoFire; }, [onAutoFire]);
  useEffect(() => { sessionStatusRef.current = session?.status; }, [session?.status]);

  // Adaptive polling cadence — re-arm interval when proximity to next race changes
  useEffect(() => {
    let cancelled = false;
    let timeoutId = null;

    const computeNextDelay = () => {
      if (!nextMarket) return POLL_RACES_MS_FAR;
      const remaining = Math.floor((nextMarket.startMs - Date.now()) / 1000);
      return remaining <= NEAR_WINDOW_SECS ? POLL_RACES_MS_NEAR : POLL_RACES_MS_FAR;
    };

    const load = async () => {
      try {
        const data = await api.betfairRaces(60);
        if (cancelled) return;
        const upcoming = (data.markets || [])
          .map((m) => ({ ...m, startMs: new Date(m.marketStartTime || m.market_start_time).getTime() }))
          .filter((m) => !isNaN(m.startMs) && m.startMs > Date.now() - 1000)
          .sort((a, b) => a.startMs - b.startMs);
        setNextMarket((prev) => {
          const next = upcoming[0] || null;
          if (prev && next && prev.market_id === next.market_id) return prev; // identity-stable
          if (!prev && !next) return prev;
          // eslint-disable-next-line no-console
          console.info("[LiveCountdown] next-market →",
            next ? `${next.event?.name || next.venue} · ${next.marketName} · ${new Date(next.startMs).toLocaleTimeString()}` : "(none)");
          return next;
        });
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e.response?.data?.detail || e.message || "Betfair unavailable");
      } finally {
        if (!cancelled) {
          timeoutId = setTimeout(load, computeNextDelay());
        }
      }
    };
    load();
    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // single mount — load() reschedules itself adaptively

  // Tick the countdown + trigger autoFire — depends ONLY on nextMarket so it
  // doesn't tear down on every onAutoFire reference change.
  useEffect(() => {
    if (!nextMarket) { setSecsToStart(null); return; }
    let prevRemaining = null;
    const tick = () => {
      const remaining = Math.floor((nextMarket.startMs - Date.now()) / 1000);
      setSecsToStart(remaining);

      const ap = autoPlaceRef.current;
      const fired = firedRef.current.has(nextMarket.market_id);
      // Fire conditions: autoPlace on, T-60..T-5 window, session active, not yet fired.
      const inWindow = remaining <= TRIGGER_AT_SECS && remaining > -5;

      if (ap && inWindow && !fired && sessionStatusRef.current === "active") {
        firedRef.current.set(nextMarket.market_id, Date.now());
        // eslint-disable-next-line no-console
        console.info("[LiveCountdown] AUTO-FIRE", {
          market_id: nextMarket.market_id,
          venue: nextMarket.event?.name || nextMarket.venue,
          remaining_secs: remaining,
        });
        try { onAutoFireRef.current?.(nextMarket); }
        catch (e) { console.error("[LiveCountdown] onAutoFire threw:", e); }
      } else if (ap && inWindow && fired && prevRemaining !== remaining && remaining % 15 === 0) {
        // Periodic diagnostic so the user can see it KNOWS it's in-window but
        // refusing to refire (race already auto-placed).
        // eslint-disable-next-line no-console
        console.debug("[LiveCountdown] skip refire", nextMarket.market_id, "remaining=", remaining);
      }
      prevRemaining = remaining;
    };
    tick();
    const id = setInterval(tick, TICK_MS);
    return () => clearInterval(id);
  }, [nextMarket]);

  if (session?.config?.mode !== "live") return null;

  const fmt = (s) => {
    if (s == null) return "—:—";
    // Stop counting once the off is reached — don't show negative numbers.
    if (s <= 0) return "00:00";
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
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
      data-next-market={nextMarket?.market_id || ""}
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
              {nextMarket.event?.name || nextMarket.venue || "Unknown track"}
            </span>
            <span className="text-xs text-zinc-400 truncate">
              {nextMarket.marketName || "Race"}
            </span>
          
            <span className="text-xs text-zinc-400 truncate">
              {nextMarket.marketName || "Race"}
            </span>
          
            <span className="text-[10px] font-mono text-zinc-500 uppercase">
              {new Date(nextMarket.startMs).toLocaleTimeString("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
              })}
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
          {past ? "IN-PLAY" : fmt(secsToStart)}
        </div>
        <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-600 mt-1">
          {past ? "settling" : "to off"}
        </div>
      </div>
    </div>
  );
};
