/**
 * SettlementBanner — tiny bottom-center pill shown while we're waiting for
 * Betfair to settle the most recent live race. Far less intrusive than a
 * full sonner toast, doesn't cover the trading journal, and updates in place.
 *
 * Driven by the most recent `poll_status` event from useSessionEvents — that
 * hook stores it on window.__lhPollStatus__ and emits a CustomEvent. We listen
 * to that here to avoid a global state lib for one transient piece of UI.
 */
import React, { useEffect, useState } from "react";
import { Hourglass } from "lucide-react";

export const SettlementBanner = () => {
  const [poll, setPoll] = useState(null);
  useEffect(() => {
    const handler = (ev) => setPoll(ev.detail || null);
    window.addEventListener("lh:poll_status", handler);
    return () => window.removeEventListener("lh:poll_status", handler);
  }, []);

  if (!poll) return null;
  if (poll.market_status === "settled" || poll.market_status === "timeout") return null;

  const fraction = Math.min(1, (poll.attempt || 0) / (poll.max_attempts || 60));

  return (
    <div
      data-testid="settlement-banner"
      className="fixed left-1/2 bottom-3 -translate-x-1/2 z-30 pointer-events-none"
    >
      <div className="bg-[#141414]/95 backdrop-blur-sm border border-[#2A2A2A] text-zinc-300 text-[11px] font-mono uppercase tracking-wider px-3 py-1.5 flex items-center gap-2 shadow-lg">
        <Hourglass className="w-3 h-3 animate-pulse text-pink-400" />
        <span>Awaiting Betfair settlement</span>
        <span className="text-pink-400">
          {poll.attempt}/{poll.max_attempts}
        </span>
        <span className="w-16 h-[3px] bg-[#0A0A0A] overflow-hidden">
          <span
            className="block h-full bg-pink-500/70 transition-all duration-300"
            style={{ width: `${fraction * 100}%` }}
          />
        </span>
      </div>
    </div>
  );
};
