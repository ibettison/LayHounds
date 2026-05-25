import React, { useEffect, useState, useCallback } from "react";
import "../App.css";
import { toast } from "sonner";
import { Play, Square, Activity, TrendingUp, TrendingDown, Wallet, Flag, Trash2, RefreshCw } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "../components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "../components/ui/alert-dialog";
import { api } from "../lib/api";
import { NewSessionDialog } from "../components/NewSessionDialog";
import { StatPanel } from "../components/StatPanel";
import { RaceCard } from "../components/RaceCard";
import { RecoveryStatus } from "../components/RecoveryStatus";
import { RaceHistory } from "../components/RaceHistory";
import { SessionList } from "../components/SessionList";
import { BetfairStatusBadge } from "../components/BetfairStatusBadge";
import { DailyChart } from "../components/DailyChart";
import { LiveCountdown } from "../components/LiveCountdown";
import { LicencePanel } from "../components/LicencePanel";
import { useSessionEvents } from "../hooks/useSessionEvents";

export default function Simulator() {
  const [sessions, setSessions] = useState([]);
  const [current, setCurrent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [batchSize, setBatchSize] = useState(1);

  const location = useLocation();
  const navigate = useNavigate();
  const [showArrival, setShowArrival] = useState(false);

  // "You've arrived" moment — fires when navigating in from the marketing site.
  useEffect(() => {
    if (location.state?.fromMarketing) {
      setShowArrival(true);
      // Clear the state so a refresh doesn't replay the animation
      navigate(location.pathname, { replace: true, state: {} });
      // Toast lands as the overlay fades
      const t1 = setTimeout(() => {
        toast.success("Welcome to your sandbox", {
          description: "Running in Free Simulator mode — no card needed.",
          duration: 5000,
        });
      }, 700);
      const t2 = setTimeout(() => setShowArrival(false), 1200);
      return () => { clearTimeout(t1); clearTimeout(t2); };
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const refreshList = useCallback(async () => {
    try {
      const list = await api.listSessions();
      setSessions(list);
      return list;
    } catch (e) {
      toast.error(`Could not load sessions: ${e.message}`);
      return [];
    }
  }, []);

  useEffect(() => {
    (async () => {
      const list = await refreshList();
      if (list.length > 0 && !current) setCurrent(list[0]);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Subscribe to live SSE events for the active session: bet placed, settlement
  // polling, race resolved, bank updates. The hook surfaces toasts for each
  // event and calls onSessionUpdate so the simulator refetches state.
  useSessionEvents(current?.id, {
    enabled: !!current,
    onSessionUpdate: useCallback(async () => {
      if (!current?.id) return;
      try {
        const fresh = await api.getSession(current.id);
        setCurrent(fresh);
        await refreshList();
      } catch (e) { /* swallow — next user action will recover */ }
    }, [current?.id, refreshList]),
  });

  const onCreated = async (session) => {
    setCurrent(session);
    await refreshList();
  };

  const onSelect = async (id) => {
    try {
      const s = await api.getSession(id);
      setCurrent(s);
    } catch (e) {
      toast.error(`Failed: ${e.message}`);
    }
  };

  const onDelete = async (id) => {
    try {
      await api.deleteSession(id);
      toast.success("Session deleted");
      const list = await refreshList();
      if (current?.id === id) setCurrent(list[0] || null);
    } catch (e) {
      toast.error(`Delete failed: ${e.message}`);
    }
  };

  const onResetAll = async () => {
    try {
      const res = await api.resetAll();
      setCurrent(null);
      await refreshList();
      toast.success(`Reset complete — ${res.deleted} session${res.deleted === 1 ? "" : "s"} cleared`);
    } catch (e) {
      toast.error(`Reset failed: ${e.message}`);
    }
  };

  const onRefreshBank = async () => {
    if (!current) return;
    try {
      const updated = await api.refreshBank(current.id);
      setCurrent(updated);
      await refreshList();
      toast.success(`Bank synced from Betfair — £${updated.bank.toFixed(2)}`);
    } catch (e) {
      const detail = e.response?.data?.detail || e.message;
      toast.error(`Could not refresh bank: ${detail}`);
    }
  };

  const runNextRace = useCallback(async (opts = {}) => {
    if (!current) return;
    const auto = opts.auto === true;
    setLoading(true);
    try {
      const updated = batchSize === 1
        ? await api.nextRace(current.id)
        : await api.runRaces(current.id, batchSize);
      setCurrent(updated);
      await refreshList();
      const racesAdded = updated.races_played - (current.races_played || 0);
      const pnlDelta = updated.total_pnl - (current.total_pnl || 0);
      if (batchSize > 1) {
        const tone = pnlDelta >= 0 ? toast.success : toast.error;
        tone(`Ran ${racesAdded} races: ${pnlDelta >= 0 ? "+" : ""}£${pnlDelta.toFixed(2)}`);
      } else {
        const last = updated.races[updated.races.length - 1];
        const prefix = auto ? "AUTO · " : "";
        if (last.pnl_change >= 0) toast.success(`${prefix}Race #${last.race_num}: +£${last.pnl_change.toFixed(2)}`);
        else toast.error(`${prefix}Race #${last.race_num}: £${last.pnl_change.toFixed(2)}`);
      }
      if (updated.status !== "active") {
        toast.warning(`Session ${updated.status.replace("_", " ").toUpperCase()}`);
      }
    } catch (e) {
      const detail = e.response?.data?.detail || e.message;
      toast.error(`${opts.auto ? "AUTO-place failed · " : ""}${detail}`);
    } finally {
      setLoading(false);
    }
  }, [current, batchSize]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-fire callback used by LiveCountdown at T-60s
  const onAutoFire = useCallback((market) => {
    if (!current || current.status !== "active") return;
    toast.message(`Auto-placing lays for ${market.venue}…`, { duration: 3000 });
    runNextRace({ auto: true });
  }, [current, runNextRace]);

  const stopSession = async () => {
    if (!current) return;
    try {
      const updated = await api.stopSession(current.id);
      setCurrent(updated);
      await refreshList();
      toast.success("Session stopped");
    } catch (e) {
      toast.error(e.message);
    }
  };

  const lastRace = current?.races?.[current.races.length - 1];
  const layedRanks = lastRace ? lastRace.bets.map((b) => b.favourite_rank) : [];

  const statusBadge = (status) => {
    const map = {
      active: { txt: "Active", cls: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" },
      stopped_win: { txt: "Stop-Win Hit", cls: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" },
      stopped_loss: { txt: "Stop-Loss Hit", cls: "bg-red-500/10 border-red-500/30 text-red-400" },
      stopped_max: { txt: "Day Complete", cls: "bg-blue-500/10 border-blue-500/30 text-blue-400" },
      stopped_manual: { txt: "Stopped", cls: "bg-zinc-500/10 border-zinc-500/30 text-zinc-400" },
    };
    return map[status] || map.active;
  };

  const inOverrun =
    current && current.status === "active" && current.races_played >= current.config.max_races;

  return (
    <div className="App min-h-screen bg-[#0A0A0A]">
      {/* "You've arrived" pink-gradient transition */}
      <AnimatePresence>
        {showArrival && (
          <motion.div
            data-testid="arrival-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="fixed inset-0 z-[100] pointer-events-none flex items-center justify-center"
            style={{
              background:
                "radial-gradient(ellipse at center, rgba(236,72,153,0.55) 0%, rgba(190,24,93,0.85) 50%, rgba(10,10,10,0.95) 100%)",
            }}
          >
            <motion.div
              initial={{ scale: 0.92, opacity: 0, y: 12 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 1.04, opacity: 0 }}
              transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
              className="text-center"
            >
              <div className="w-16 h-16 mx-auto mb-5 bg-white grid place-items-center shadow-2xl">
                <Activity className="w-8 h-8 text-pink-500" />
              </div>
              <div className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-white">
                You're in.
              </div>
              <div className="text-xs font-mono uppercase tracking-[0.3em] text-pink-100 mt-3 font-semibold">
                Loading your sandbox…
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <header className="border-b border-[#2A2A2A] bg-[#0A0A0A]" data-testid="app-header">
        <div className="max-w-[1600px] mx-auto px-6 py-5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3" data-testid="header-home-link">
            <div className="w-10 h-10 bg-pink-600 flex items-center justify-center">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-display text-3xl font-black uppercase tracking-tighter leading-none">
                Lay-Hounds
              </div>
              <div className="label-xs">Greyhound Recovery Simulator</div>
            </div>
          </Link>
          <div className="flex items-center gap-3">
            <BetfairStatusBadge />
            {current && current.config.mode === "live" && (
              <Button
                data-testid="refresh-bank-btn"
                variant="ghost"
                onClick={onRefreshBank}
                className="rounded-none border border-[#2A2A2A] text-zinc-400 hover:text-pink-400 hover:bg-pink-500/10 hover:border-pink-500/40 font-bold uppercase tracking-wider text-xs"
                title="Sync bank with Betfair available-to-bet balance"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Sync Bank
              </Button>
            )}
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  data-testid="reset-all-btn"
                  variant="ghost"
                  disabled={sessions.length === 0}
                  className="rounded-none border border-[#2A2A2A] text-zinc-400 hover:text-red-400 hover:bg-red-500/10 hover:border-red-500/40 font-bold uppercase tracking-wider text-xs disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Reset
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent
                data-testid="reset-confirm-dialog"
                className="bg-[#141414] border-[#2A2A2A] rounded-none text-white"
              >
                <AlertDialogHeader>
                  <AlertDialogTitle className="font-display uppercase text-2xl tracking-tight text-red-400">
                    Reset All Data?
                  </AlertDialogTitle>
                  <AlertDialogDescription className="text-zinc-400 font-mono text-xs leading-relaxed">
                    This permanently deletes <span className="text-red-400 font-bold">all {sessions.length} saved session{sessions.length === 1 ? "" : "s"}</span>, including races, recovery chains, P&amp;L history and bank carryover. This cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel
                    data-testid="reset-cancel-btn"
                    className="rounded-none bg-transparent border-[#2A2A2A] text-zinc-400 hover:bg-[#1C1C1C] hover:text-white"
                  >
                    Cancel
                  </AlertDialogCancel>
                  <AlertDialogAction
                    data-testid="reset-confirm-btn"
                    onClick={onResetAll}
                    className="rounded-none bg-red-600 hover:bg-red-500 text-white font-bold uppercase tracking-wider"
                  >
                    Yes, wipe everything
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            <NewSessionDialog onCreated={onCreated} />
          </div>
        </div>
      </header>

      {/* Live race countdown (live mode only) */}
      {current && current.config.mode === "live" && current.status === "active" && (
        <div className="max-w-[1600px] mx-auto px-6 pt-4">
          <LiveCountdown
            session={current}
            autoPlace={!!current.config.auto_place}
            onAutoFire={onAutoFire}
          />
        </div>
      )}

      <main className="max-w-[1600px] mx-auto px-6 py-6 grid grid-cols-12 gap-4">
        {/* Left column */}
        <aside className="col-span-12 lg:col-span-3 space-y-4">
          <LicencePanel />
          <SessionList
            sessions={sessions}
            currentId={current?.id}
            onSelect={onSelect}
            onDelete={onDelete}
          />
          {current && (
            <div className="bg-[#141414] border border-[#2A2A2A] p-4">
              <div className="label-xs mb-3">Config</div>
              <div className="space-y-2 text-sm">
                <ConfRow l="Mode" v={(current.config.mode || "simulator").replace("_", "-")} />
                <ConfRow l="Stake" v={`£${current.config.stake.toFixed(2)}`} />
                <ConfRow l="Commission" v={`${((current.config.commission_rate ?? 0.05) * 100).toFixed(1)}%`} />
                <ConfRow l="Liab Cap" v={(current.config.max_liability_cap ?? 0) > 0 ? `£${current.config.max_liability_cap.toFixed(2)}` : "off"} />
                {current.config.mode === "live" && (
                  <ConfRow l="Auto-place" v={current.config.auto_place ? "ON · T-60s" : "off"} />
                )}
                {current.config.mode === "live" && current.config.stake < 1.0 && (
                  <ConfRow l="Sub-£1 placement" v="Auto-parking" />
                )}
                <ConfRow l="# Favs" v={current.config.num_favourites} />
                <ConfRow l="Stop Win" v={`£${current.config.stop_win.toFixed(2)}`} />
                <ConfRow l="Stop Loss" v={`£${current.config.stop_loss.toFixed(2)}`} />
                <ConfRow l="Max Races" v={current.config.max_races} />
                <ConfRow l="Start Bank" v={`£${current.config.starting_bank.toFixed(2)}`} />
              </div>
            </div>
          )}
        </aside>

        {/* Center + right */}
        <section className="col-span-12 lg:col-span-9 space-y-4">
          {!current && (
            <div className="bg-[#141414] border border-[#2A2A2A] p-16 text-center">
              <Flag className="w-14 h-14 mx-auto text-zinc-700 mb-4" />
              <div className="font-display text-3xl uppercase tracking-tight mb-2">
                Welcome to Lay-Hounds
              </div>
              <div className="text-zinc-400 max-w-md mx-auto mb-6">
                A controlled environment to test configurable lay recovery strategies on simulated UK
                greyhound racing. Start a session to begin.
              </div>
              <NewSessionDialog onCreated={onCreated} />
            </div>
          )}

          {current && (
            <>
              {/* Status bar */}
              <div
                className="bg-[#141414] border border-[#2A2A2A] p-4 flex items-center justify-between flex-wrap gap-3"
                data-testid="status-bar"
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`px-3 py-1 border text-xs font-bold uppercase tracking-wider ${
                      statusBadge(current.status).cls
                    }`}
                    data-testid="session-status-badge"
                  >
                    {statusBadge(current.status).txt}
                  </div>
                  {inOverrun && (
                    <div
                      data-testid="overrun-badge"
                      className="px-3 py-1 border border-amber-500/30 bg-amber-500/10 text-amber-400 text-xs font-bold uppercase tracking-wider"
                    >
                      Recovery Overrun
                    </div>
                  )}
                  <div className="text-sm text-zinc-400 font-mono">
                    Race {current.races_played}/{current.config.max_races}
                    {inOverrun && " (+overrun)"}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center bg-[#0A0A0A] border border-[#2A2A2A]" data-testid="batch-size-selector">
                    {[1, 5, 10, 25, 50].map((n) => (
                      <button
                        key={n}
                        type="button"
                        data-testid={`batch-${n}`}
                        onClick={() => setBatchSize(n)}
                        className={`px-2.5 py-1 text-xs font-mono font-bold transition-colors ${
                          batchSize === n
                            ? "bg-pink-500/20 text-pink-400"
                            : "text-zinc-500 hover:text-white"
                        }`}
                      >
                        ×{n}
                      </button>
                    ))}
                  </div>
                  <Button
                    data-testid="next-race-btn"
                    onClick={runNextRace}
                    disabled={loading || current.status !== "active"}
                    className="bg-pink-600 hover:bg-pink-500 text-white font-bold uppercase tracking-wider rounded-none border-b-2 border-pink-800 active:translate-y-[1px] active:border-b-0 disabled:opacity-40"
                  >
                    <Play className="w-4 h-4 mr-2" />
                    {loading ? "Running…" : `Run ${batchSize === 1 ? "Next Race" : batchSize + " Races"}`}
                  </Button>
                  <Button
                    data-testid="stop-session-btn"
                    onClick={stopSession}
                    disabled={current.status !== "active"}
                    variant="ghost"
                    className="bg-[#1C1C1C] hover:bg-[#2A2A2A] text-white border border-[#2A2A2A] rounded-none disabled:opacity-30"
                  >
                    <Square className="w-4 h-4 mr-2" />
                    Stop
                  </Button>
                </div>
              </div>

              {/* Stats grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatPanel
                  testId="stat-bank"
                  label="Bank"
                  value={`£${current.bank.toFixed(2)}`}
                  sub={`from £${current.config.starting_bank.toFixed(2)}`}
                  tone="default"
                />
                <StatPanel
                  testId="stat-pnl"
                  label="Total P&L"
                  value={`${current.total_pnl >= 0 ? "+" : ""}£${current.total_pnl.toFixed(2)}`}
                  sub={
                    current.total_pnl >= 0
                      ? `${((current.total_pnl / current.config.stop_win) * 100).toFixed(0)}% to stop-win`
                      : `${((current.total_pnl / -current.config.stop_loss) * 100).toFixed(0)}% to stop-loss`
                  }
                  tone={current.total_pnl >= 0 ? "win" : "loss"}
                />
                <StatPanel
                  testId="stat-staked"
                  label="Total Staked"
                  value={`£${current.total_staked.toFixed(2)}`}
                  sub={`liability £${current.total_liability_risked.toFixed(2)}`}
                  tone="amber"
                />
                <StatPanel
                  testId="stat-races"
                  label="Races"
                  value={`${current.races_played}`}
                  sub={`of ${current.config.max_races} max`}
                  tone="pink"
                />
              </div>

              {/* Race + Recovery side-by-side */}
              <div className="grid grid-cols-12 gap-4">
                <div className="col-span-12 xl:col-span-8">
                  <RaceCard race={lastRace} layedRanks={layedRanks} />
                </div>
                <div className="col-span-12 xl:col-span-4 space-y-4">
                  <RecoveryStatus chains={current.recovery_chains} maxRecoveryLevel={current.config.max_recovery_level || 3} />
                  <RaceHistory races={current.races} />
                </div>
              </div>

              {/* Daily trading journal / cross-session P&L */}
              <DailyChart refreshKey={current.races_played + "_" + current.status} />
            </>
          )}
        </section>
      </main>

      <footer className="border-t border-[#2A2A2A] bg-[#0A0A0A] mt-8">
        <div className="max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-between text-xs text-zinc-500 font-mono">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5"><Wallet className="w-3 h-3" /> Simulator only — no real money</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5"><TrendingUp className="w-3 h-3 text-emerald-400" /> lay won = stake collected</span>
            <span className="flex items-center gap-1.5"><TrendingDown className="w-3 h-3 text-red-400" /> lay lost = liability paid</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

const ConfRow = ({ l, v }) => (
  <div className="flex items-center justify-between text-sm">
    <span className="label-xs">{l}</span>
    <span className="font-mono">{v}</span>
  </div>
);
