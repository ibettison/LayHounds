import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { API, api } from "../lib/api";

const PREVIEW_OPEN_SECS = 300;
const POLL_NEAR_MS = 6_000;
const POLL_FAR_MS = 30_000;

const normalizeMarket = (market) => {
  if (!market) return null;
  return {
    ...market,
    market_id: market.marketId || market.market_id || "",
    startMs: new Date(market.marketStartTime || market.market_start_time).getTime(),
  };
};

const isBetfairMode = (mode) => ["live", "paper_live"].includes(mode);

export const UpcomingRacePreview = ({ session }) => {
  const [nextMarket, setNextMarket] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState(null);
  const [now, setNow] = useState(Date.now());
  const prevOddsRef = useRef(new Map());

  const mode = session?.config?.mode;
  const numFavs = session?.config?.num_favourites || 1;

  useEffect(() => {
    if (!isBetfairMode(mode)) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [mode]);

  useEffect(() => {
    if (!isBetfairMode(mode)) return undefined;
    let cancelled = false;
    let timer = null;

    const tick = async () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      let soonest = null;
      try {
        const data = await api.betfairRaces(60);
        if (cancelled) return;
        const upcoming = (data.markets || [])
          .map(normalizeMarket)
          .filter((m) => m && m.market_id && !isNaN(m.startMs) && m.startMs > Date.now() - 5000)
          .sort((a, b) => a.startMs - b.startMs);
        soonest = upcoming[0] || null;
        setNextMarket((prev) => (prev && soonest && prev.market_id === soonest.market_id ? prev : soonest));
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e.response?.data?.detail || e.message);
      } finally {
        if (!cancelled) {
          const remaining = soonest ? Math.floor((soonest.startMs - Date.now()) / 1000) : 9999;
          timer = setTimeout(tick, remaining < PREVIEW_OPEN_SECS ? POLL_NEAR_MS : POLL_FAR_MS);
        }
      }
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [mode]);

  const marketId = nextMarket?.market_id;
  const startMs = nextMarket?.startMs;
  const remaining = startMs ? Math.floor((startMs - now) / 1000) : 9999;
  const inPreviewWindow = remaining <= PREVIEW_OPEN_SECS && remaining > -30;

  useEffect(() => {
    if (!marketId || !startMs) {
      setSnapshot(null);
      return undefined;
    }
    if (!inPreviewWindow) {
      setSnapshot(null);
      return undefined;
    }

    let cancelled = false;
    let timer = null;

    const tick = async () => {
      try {
        const { data } = await axios.get(`${API}/betfair/market/${marketId}/preview`);
        if (cancelled) return;
        const next = new Map();
        (data.runners || []).forEach((r) => next.set(r.selection_id, r.odds));
        const prev = prevOddsRef.current;
        const annotated = (data.runners || []).map((r) => {
          const before = prev.get(r.selection_id);
          let trend = "flat";
          if (before != null && r.odds > before + 0.001) trend = "drift";
          else if (before != null && r.odds < before - 0.001) trend = "steam";
          return { ...r, trend };
        });
        prevOddsRef.current = next;
        setSnapshot({ ...data, runners: annotated });
      } catch (e) {
        if (cancelled) return;
        const detail = e.response?.data?.detail || e.message;
        console.warn("[UpcomingRacePreview] preview fetch failed:", detail);
        setSnapshot((s) => s);
      } finally {
        if (!cancelled) timer = setTimeout(tick, POLL_NEAR_MS);
      }
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [marketId, startMs, inPreviewWindow]);

  if (!isBetfairMode(mode)) return null;
  if (error && !nextMarket) {
    return (
      <div className="bg-[#141414] border border-red-500/30 p-3 text-xs text-red-400" data-testid="upcoming-race-preview">
        Betfair races unreachable: {error}
      </div>
    );
  }
  if (!nextMarket) {
    return (
      <div className="bg-[#141414] border border-[#2A2A2A] p-3 text-xs text-zinc-500" data-testid="upcoming-race-preview">
        Looking for upcoming UK greyhound markets...
      </div>
    );
  }

  const minsAway = Math.max(0, Math.round(remaining / 60));
  const targetRunners = snapshot?.runners
    ? snapshot.runners
        .filter((r) => r.favourite_rank <= numFavs)
        .sort((a, b) => a.favourite_rank - b.favourite_rank)
    : [];

  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="upcoming-race-preview">
      <div className="flex items-center justify-between bg-[#0A0A0A] border-b border-[#2A2A2A] px-3 py-2 gap-3">
        <div className="min-w-0">
          <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">
            {inPreviewWindow ? "Upcoming - live prices" : "Next race"}
          </div>
          <div className="flex items-center gap-2 mt-0.5 min-w-0">
            <span className="font-display font-bold text-white text-base truncate">
              {nextMarket.event?.name || nextMarket.venue || "-"}
            </span>
            <span className="text-xs text-zinc-400 truncate">{nextMarket.marketName}</span>
            {snapshot?.category && (
              <span className="text-[9px] font-mono font-bold uppercase tracking-wider text-pink-300/80 shrink-0">
                {snapshot.category.grade} - {snapshot.category.distance_m}m
              </span>
            )}
          </div>
        </div>
        <div className="text-right text-[10px] font-mono text-zinc-500 shrink-0">
          {inPreviewWindow
            ? snapshot?.last_updated
              ? <>updated {new Date(snapshot.last_updated).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</>
              : <>loading prices</>
            : <>~{minsAway} min away - preview opens at T-5min</>}
        </div>
      </div>

      {inPreviewWindow && (
        !snapshot ? (
          <div className="px-3 py-2 text-xs text-zinc-500">Loading live prices...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-1.5 p-2">
            {targetRunners.map((r) => (
              <div
                key={r.selection_id}
                className="bg-pink-500/5 border border-pink-500/20 px-2 py-1.5 flex items-center gap-2 min-w-0"
                data-testid={`preview-runner-${r.trap}`}
              >
                <span className={`trap-${r.trap} w-5 h-5 inline-flex items-center justify-center font-mono text-xs font-bold shrink-0`}>
                  {r.trap}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-white text-xs truncate">{r.name}</div>
                  <div className="text-[9px] font-mono text-pink-300/80 uppercase">Fav #{r.favourite_rank}</div>
                </div>
                <div className="text-right font-mono shrink-0 text-xs">
                  <span className={
                    r.trend === "steam" ? "text-emerald-400"
                      : r.trend === "drift" ? "text-amber-400"
                        : "text-white"
                  }>
                    L {Number(r.odds || 0).toFixed(2)}
                  </span>
                  {r.trend === "steam" && <span className="text-emerald-400 ml-1">v</span>}
                  {r.trend === "drift" && <span className="text-amber-400 ml-1">^</span>}
                  <div className="text-[9px] text-zinc-500">
                    B {r.back_odds != null ? Number(r.back_odds).toFixed(2) : "-"}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
};
