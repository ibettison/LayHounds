import React, { useEffect, useState, useRef } from "react";
import axios from "axios";
import { Trophy } from "lucide-react";
import { API, api } from "../lib/api";

const PREVIEW_OPEN_SECS = 300;      // open detailed preview ≥ 5 min before the off
const POLL_NEAR_MS = 6_000;         // refresh runners + prices every 6s when in preview window
const POLL_FAR_MS = 30_000;         // refresh upcoming-races list every 30s otherwise

const normalizeMarket = (market) => {
  if (!market) return null;
  return {
    ...market,
    market_id: market.marketId || market.market_id || "",
    startMs: new Date(market.marketStartTime || market.market_start_time).getTime(),
  };
};

/**
 * UpcomingRacePreview — self-sufficient component that:
 *   • Polls /api/betfair/races to find the soonest upcoming UK greyhound market.
 *   • When that market is within 5 minutes, ALSO polls
 *     /api/betfair/market/{id}/preview every 6s for live runners + lay/back prices.
 *   • Highlights the top `num_favourites` runners in pink with a Fav # badge.
 *   • Shows price drift (▲ amber) / steam (▼ green) arrows between polls.
 *
 * Renders even when far from the next race (collapsed banner) so the user can
 * see at a glance that the panel is alive and which race is next.
 */
export const UpcomingRacePreview = ({ session }) => {
  const [nextMarket, setNextMarket] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState(null);
  const prevOddsRef = useRef(new Map());

  const numFavs = session?.config?.num_favourites || 1;

  // --- Poll the upcoming-races list ---
  useEffect(() => {
    if (session?.config?.mode !== "live") return undefined;
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
        const detail = e.response?.data?.detail || e.message;
        setError(detail);
      } finally {
        if (!cancelled) {
          const remaining = soonest ? Math.floor((soonest.startMs - Date.now()) / 1000) : 9999;
          timer = setTimeout(tick, remaining < PREVIEW_OPEN_SECS ? POLL_NEAR_MS : POLL_FAR_MS);
        }
      }
    };
    tick();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.config?.mode]);

  // --- Poll the detailed market preview when within 5 min ---
  const marketId = nextMarket?.market_id;
  const startMs = nextMarket?.startMs;

  useEffect(() => {
    if (!marketId || !startMs) { setSnapshot(null); return undefined; }
    const remaining = Math.floor((startMs - Date.now()) / 1000);
    if (remaining > PREVIEW_OPEN_SECS || remaining < -30) {
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
        // eslint-disable-next-line no-console
        console.warn("[UpcomingRacePreview] preview fetch failed:", detail);
        setSnapshot((s) => s);  // keep last good snapshot if any
      } finally {
        if (!cancelled) timer = setTimeout(tick, POLL_NEAR_MS);
      }
    };
    tick();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [marketId, startMs]);

  if (session?.config?.mode !== "live") return null;
  if (error && !nextMarket) {
    return (
      <div className="bg-[#141414] border border-red-500/30 p-3 text-xs text-red-400" data-testid="upcoming-race-preview">
        Live races unreachable: {error}
      </div>
    );
  }
  if (!nextMarket) {
    return (
      <div className="bg-[#141414] border border-[#2A2A2A] p-3 text-xs text-zinc-500" data-testid="upcoming-race-preview">
        Looking for upcoming UK greyhound markets…
      </div>
    );
  }

  const remaining = Math.floor((startMs - Date.now()) / 1000);
  const inPreviewWindow = remaining <= PREVIEW_OPEN_SECS && remaining > -30;
  const minsAway = Math.max(0, Math.round(remaining / 60));

  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="upcoming-race-preview">
      <div className="flex items-center justify-between bg-[#0A0A0A] border-b border-[#2A2A2A] p-3">
        <div className="min-w-0">
          <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">
            {inPreviewWindow ? "Upcoming · live prices" : "Next race"}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="font-display font-bold text-white text-base truncate">
              {nextMarket.event?.name || nextMarket.venue || "—"}
            </span>
            <span className="text-xs text-zinc-400 truncate">{nextMarket.marketName}</span>
            {snapshot?.category && (
              <span className="text-[9px] font-mono font-bold uppercase tracking-wider text-pink-300/80">
                {snapshot.category.grade} · {snapshot.category.distance_m}m
              </span>
            )}
          </div>
        </div>
        <div className="text-right text-[10px] font-mono text-zinc-500 shrink-0">
          {inPreviewWindow ? (
            snapshot?.last_updated && (
              <>updated {new Date(snapshot.last_updated).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</>
            )
          ) : (
            <>~{minsAway} min away · preview opens at T-5min</>
          )}
        </div>
      </div>

      {inPreviewWindow && (
        !snapshot ? (
          <div className="p-4 text-xs text-zinc-500">Loading live prices…</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-[#0A0A0A] text-zinc-500">
              <tr className="text-[10px] uppercase tracking-wider">
                <th className="p-2 text-left">Trap</th>
                <th className="p-2 text-left">Greyhound</th>
                <th className="p-2 text-right">Lay</th>
                <th className="p-2 text-right">Back</th>
                <th className="p-2 text-right">Fav</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2A2A2A]">
              {snapshot.runners.map((r) => {
                const isTopFav = r.favourite_rank <= numFavs;
                return (
                  <tr key={r.selection_id} className={isTopFav ? "bg-pink-500/5" : ""} data-testid={`preview-runner-${r.trap}`}>
                    <td className="p-2">
                      <span className={`trap-${r.trap} w-5 h-5 inline-flex items-center justify-center font-mono text-xs font-bold`}>
                        {r.trap}
                      </span>
                    </td>
                    <td className="p-2 text-white truncate">{r.name}</td>
                    <td className="p-2 text-right font-mono">
                      <span className={
                        r.trend === "steam" ? "text-emerald-400"
                          : r.trend === "drift" ? "text-amber-400"
                            : "text-white"
                      }>
                        {Number(r.odds || 0).toFixed(2)}
                      </span>
                      {r.trend === "steam" && <span className="text-emerald-400 ml-1">▼</span>}
                      {r.trend === "drift" && <span className="text-amber-400 ml-1">▲</span>}
                    </td>
                    <td className="p-2 text-right font-mono text-zinc-500">
                      {r.back_odds != null ? Number(r.back_odds).toFixed(2) : "—"}
                    </td>
                    <td className="p-2 text-right">
                      {isTopFav ? (
                        <span className="inline-flex items-center gap-1 bg-pink-500/15 text-pink-300 border border-pink-500/30 px-2 py-0.5 text-[10px] font-mono font-bold uppercase">
                          <Trophy className="w-3 h-3" />
                          Fav #{r.favourite_rank}
                        </span>
                      ) : (
                        <span className="text-zinc-600 font-mono text-[10px]">#{r.favourite_rank}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )
      )}
    </div>
  );
};
