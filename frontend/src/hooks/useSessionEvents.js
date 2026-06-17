/**
 * useSessionEvents — subscribes to the per-session Server-Sent-Events
 * stream and translates Betfair-side events into UI feedback:
 *
 *   bet_placed     → blue "BET PLACED" toast with stake + liability totals.
 *   poll_status    → muted "waiting for settlement, attempt X/Y" toast (debounced).
 *   race_resulted  → green/red toast + invalidates the session so the UI repaints.
 *                    Toasts can be suppressed during simulator batch runs.
 *   bank_updated   → silent — caller refetches via onSessionUpdate.
 *   error          → red toast.
 *
 * EventSource auto-reconnects on transient drop. We tear it down on
 * sessionId change / unmount.
 */
import { useEffect } from "react";
import { toast } from "sonner";
import { API } from "../lib/api";

export const useSessionEvents = (
  sessionId,
  { onSessionUpdate, enabled = true, suppressRaceToastsRef = null } = {}
) => {
  useEffect(() => {
    if (!enabled || !sessionId) return undefined;
    const url = `${API}/sessions/${sessionId}/events`;
    const es = new EventSource(url, { withCredentials: false });

    es.addEventListener("bet_placed", (e) => {
      try {
        const d = JSON.parse(e.data);
        const stake = Number(d.total_stake || 0).toFixed(2);
        const liab = Number(d.total_liability || 0).toFixed(2);
        const cat = d.category ? `${d.category.grade} · ${d.category.distance_m}m` : "";
        toast.success(
          `LIVE · BET PLACED — Race #${d.race_num} ${d.venue} ${cat}`.trim(),
          {
            description: `${d.bets.length} lay${d.bets.length > 1 ? "s" : ""} · stake £${stake} · liability £${liab}`,
            duration: 7000,
            id: `bet-placed-${d.race_num}`,
          }
        );
      } catch (err) { /* ignore parse errors */ }
    });

    es.addEventListener("poll_status", (e) => {
      try {
        const d = JSON.parse(e.data);
        // Drive the compact SettlementBanner via a window event — far less
        // intrusive than a full sonner toast.
        window.dispatchEvent(
          new CustomEvent("lh:poll_status", {
            detail: {
              ...d,
              display_message:
                d.market_status === "market_closed_waiting_settlement"
                  ? "Race finished — waiting for Betfair settlement"
                  : "Awaiting Betfair settlement",
            },
          })
        );
      } catch (err) { /* ignore */ }
    });

    es.addEventListener("race_resulted", (e) => {
      try {
        const d = JSON.parse(e.data);
        // Auto-dismiss the bottom-center settlement banner via clearing event
        window.dispatchEvent(new CustomEvent("lh:poll_status", { detail: { market_status: "settled" } }));
        if (!suppressRaceToastsRef?.current) {
          const tone = d.pnl_change >= 0 ? toast.success : toast.error;
          const prefix = d.source === "live_settled" ? "LIVE SETTLED · " : "";
          tone(
            `${prefix}Race #${d.race_num}: ${d.pnl_change >= 0 ? "+" : ""}£${Number(d.pnl_change || 0).toFixed(2)}`,
            {
              description: d.winner_name
                ? `Trap ${d.winning_trap} ${d.winner_name} @${Number(d.winner_odds || 0).toFixed(2)} · bank £${Number(d.bank_after || 0).toFixed(2)}`
                : `Bank £${Number(d.bank_after || 0).toFixed(2)}`,
              duration: 6000,
            }
          );
        }
        if (onSessionUpdate) onSessionUpdate({ reason: "race_resulted" });

        window.dispatchEvent(
          new CustomEvent("lh:race_resulted", {
            detail: {
              race_num: d.race_num,
            },
          })
        );
      } catch (err) { /* ignore */ }
    });

    es.addEventListener("bank_updated", () => {
      if (onSessionUpdate) onSessionUpdate({ reason: "bank_updated" });
    });

    es.addEventListener("error", (e) => {
      // Don't toast on the implicit transport-error frame — it has no data.
      if (e.data) {
        try {
          const d = JSON.parse(e.data);
          if (d.message) toast.error(`Live error · ${d.message}`);
        } catch (err) { /* ignore */ }
      }
    });

    es.onerror = () => {
      // EventSource will auto-reconnect; no toast.
    };

    return () => {
      es.close();
    };
  }, [sessionId, enabled]); // eslint-disable-line react-hooks/exhaustive-deps
};
