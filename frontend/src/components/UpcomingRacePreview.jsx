import React, { useEffect, useState, useRef } from "react";
import axios from "axios";
import { Trophy } from "lucide-react";
import { API } from "../lib/api";

const PREVIEW_OPEN_SECS = 300;     // open preview ≥ 5 min before the off
const POLL_MS = 6_000;             // refresh runners + prices every 6 s

/**
 * UpcomingRacePreview — when a live session is active and the next race
 * is within 5 minutes, render a live runners table with selection_id,
 * trap, name, current best lay-price, and a "FAV #1 / FAV #2" badge for
 * the top configured number of favourites.
 *
 * Hides itself when there's no `nextMarket` OR > 5 min to off OR session
 * is not live mode — so it's a no-op in simulator sessions.
 */
export const UpcomingRacePreview = ({ session, nextMarket }) => {
  const [snapshot, setSnapshot] = useState(null);  // { runners, last_updated, category }
  const [error, setError] = useState(null);
  const prevOddsRef = useRef(new Map());           // selection_id → previous odds (for delta arrows)

  const numFavs = session?.config?.num_favourites || 1;
  const marketId = nextMarket?.market_id;
  const startMs = nextMarket?.startMs;

  // Only run when live + market in 5 min window
  const eligible = (() => {
    if (!nextMarket || !marketId || !startMs) return false;
    if (session?.config?.mode !== "live") return false;
    const remaining = Math.floor((startMs - Date.now()) / 1000);
    return remaining <= PREVIEW_OPEN_SECS && remaining > -10;
  })();

  useEffect(() => {
    if (!eligible) { setSnapshot(null); setError(null); return undefined; }
    let cancelled = false;
    let timer = null;

    const tick = async () => {
      try {
        const { data } = await axios.get(`${API}/betfair/market/${marketId}/preview`);
        if (cancelled) return;
        // Compute price-delta arrows for each runner
        const next = new Map();
        data.runners.forEach((r) => next.set(r.selection_id, r.odds));
        const prev = prevOddsRef.current;
        const annotated = data.runners.map((r) => {
          const before = prev.get(r.selection_id);
          let trend = "flat";
          if (before != null && r.odds > before + 0.001) trend = "drift";
          else if (before != null && r.odds < before - 0.001) trend = "steam";
          return { ...r, trend };
        });
        prevOddsRef.current = next;
        setSnapshot({ ...data, runners: annotated });
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e.response?.data?.detail || e.message);
      } finally {
        if (!cancelled) timer = setTimeout(tick, POLL_MS);
      }
    };
    tick();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [eligible, marketId]);

  if (!eligible) return null;

  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="upcoming-race-preview">
      <div className="flex items-center justify-between bg-[#0A0A0A] border-b border-[#2A2A2A] p-3">
        <div>
          <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">Upcoming · live prices</div>
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
        <div className="text-right text-[10px] font-mono text-zinc-500">
          {snapshot?.last_updated && (
            <>updated {new Date(snapshot.last_updated).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</>
          )}
          <div className="text-[9px] mt-0.5 text-zinc-600">refresh 6s</div>
        </div>
      </div>

      {error ? (
        <div className="p-4 text-xs text-red-400">{error}</div>
      ) : !snapshot ? (
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
      )}
    </div>
  );
};
