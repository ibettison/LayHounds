import React, { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
  DialogDescription,
} from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Checkbox } from "../components/ui/checkbox";
import { Switch } from "../components/ui/switch";
import { Plus, AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { CapPreview } from "./CapPreview";

const MODES = [
  { id: "simulator", label: "Simulator", desc: "Fake UK greyhound races. No Betfair connection needed." },
  { id: "paper_live", label: "Paper-Live", desc: "Real Betfair odds + races, bets simulated. No real money." },
  { id: "live", label: "Live", desc: "REAL LAY BETS placed on Betfair. Real money at risk." },
];

const STAKES = [0.05, 0.50, 1.00, 1.50, 2.00];

export const NewSessionDialog = ({ onCreated }) => {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [betfairOk, setBetfairOk] = useState(false);
  const [form, setForm] = useState({
    starting_bank: 10,
    num_favourites: 2,
    stop_win: 5,
    stop_loss: 5,
    max_races: 20,
    mode: "simulator",
    max_liability_cap: 5,
    risk_accepted: false,
    stake: 0.05,
    commission_rate: 0.05,
    odds_min: 1.01,
    odds_max: 10.0,
    max_recovery_level: 3,
    auto_place: false,
    live_price_chase: true,
    live_price_chase_ticks: 6,
    live_price_chase_seconds: 45,
  });

  useEffect(() => {
    if (!open) return;
    api.betfairStatus()
      .then((s) => setBetfairOk(s.configured && s.logged_in))
      .catch(() => setBetfairOk(false));
    // Pre-fill starting bank from prior session's ending bank
    api.currentBank()
      .then((d) => {
        if (d && typeof d.bank === "number") {
          setForm((p) => ({ ...p, starting_bank: Number(d.bank.toFixed(2)) }));
        }
      })
      .catch(() => {});
  }, [open]);

  const update = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const canSubmit = () => {
    if (form.mode === "live" && !form.risk_accepted) return false;
    return true;
  };

  const submit = async () => {
    setLoading(true);
    try {
      const session = await api.createSession({
        ...form,
        starting_bank: parseFloat(form.starting_bank),
        num_favourites: parseInt(form.num_favourites),
        stop_win: parseFloat(form.stop_win),
        stop_loss: parseFloat(form.stop_loss),
        max_races: parseInt(form.max_races),
        max_liability_cap: parseFloat(form.max_liability_cap),
        live_price_chase_ticks: parseInt(form.live_price_chase_ticks),
        live_price_chase_seconds: parseInt(form.live_price_chase_seconds),
      });
      toast.success("Session created");
      setOpen(false);
      onCreated?.(session);
    } catch (e) {
      toast.error(`Failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const inputCls =
    "bg-[#0A0A0A] border-[#2A2A2A] text-white font-mono rounded-none focus:border-pink-500 focus:ring-1 focus:ring-pink-500";

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          data-testid="open-new-session-btn"
          className="bg-pink-600 hover:bg-pink-500 text-white font-bold uppercase tracking-wider rounded-none border-b-2 border-pink-800 active:translate-y-[1px] active:border-b-0"
        >
          <Plus className="w-4 h-4 mr-2" /> New Session
        </Button>
      </DialogTrigger>
      <DialogContent
        data-testid="new-session-dialog"
        className="bg-[#141414] border-[#2A2A2A] rounded-none text-white max-w-lg max-h-[90vh] overflow-y-auto"
      >
        <DialogHeader>
          <DialogTitle className="font-display uppercase text-2xl tracking-tight">
            New Session
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            Choose mode, configure strategy. Stake is fixed at £0.05.
          </DialogDescription>
        </DialogHeader>

        {/* Mode selector */}
        <div className="space-y-2 pt-2">
          <Label className="label-xs">Mode</Label>
          <div className="grid grid-cols-3 gap-2">
            {MODES.map((m) => {
              const disabled = !betfairOk && (m.id === "paper_live" || m.id === "live");
              const active = form.mode === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  data-testid={`mode-${m.id}`}
                  disabled={disabled}
                  onClick={() => update("mode", m.id)}
                  className={`p-3 border text-left transition-colors ${
                    active
                      ? "border-pink-500 bg-pink-500/10"
                      : "border-[#2A2A2A] hover:bg-[#1C1C1C]"
                  } ${disabled ? "opacity-40 cursor-not-allowed" : ""}`}
                >
                  <div className="font-display uppercase text-sm font-bold">{m.label}</div>
                  <div className="text-[10px] text-zinc-500 mt-1 leading-tight">{m.desc}</div>
                </button>
              );
            })}
          </div>
          {!betfairOk && (
            <div className="text-[10px] text-amber-400/80 font-mono">
              Betfair not connected — paper-live and live modes disabled.
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4 pt-2">
          <div className="space-y-1.5 col-span-2">
            <Label className="label-xs">Stake per Bet £</Label>
            <div className="grid grid-cols-5 gap-1.5">
              {STAKES.map((s) => {
                const active = Math.abs(form.stake - s) < 0.001;
                return (
                  <button
                    key={s}
                    type="button"
                    data-testid={`stake-${s.toFixed(2)}`}
                    onClick={() => update("stake", s)}
                    className={`p-2 border font-mono text-sm transition-colors ${
                      active
                        ? "border-pink-500 bg-pink-500/10 text-pink-400 font-bold"
                        : "border-[#2A2A2A] hover:bg-[#1C1C1C] text-zinc-400"
                    }`}
                  >
                    £{s.toFixed(2)}
                  </button>
                );
              })}
            </div>
            <div className="text-[10px] text-zinc-500 font-mono">
              Target profit per won bet = stake. Recovery stake = prev_liability + prev_stake + stake.
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="label-xs">
              Starting Bank £
              {(form.mode === "paper_live" || form.mode === "live") && (
                <span className="ml-1.5 text-pink-400 normal-case tracking-normal">(from Betfair)</span>
              )}
            </Label>
            {form.mode === "simulator" ? (
              <Input data-testid="input-starting-bank" type="number" step="0.01"
                value={form.starting_bank} onChange={(e) => update("starting_bank", e.target.value)}
                className={inputCls} />
            ) : (
              <div data-testid="starting-bank-live" className={`${inputCls} flex items-center justify-between !cursor-default`}>
                <span className="text-pink-400 font-bold">
                  Live Betfair balance
                </span>
                <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
                  auto-synced
                </span>
              </div>
            )}
          </div>
          <div className="space-y-1.5">
            <Label className="label-xs"># Favourites</Label>
            <Input data-testid="input-num-favourites" type="number" min="1" max="4"
              value={form.num_favourites} onChange={(e) => update("num_favourites", e.target.value)}
              className={inputCls} />
          </div>
          <div className="space-y-1.5">
            <Label className="label-xs">Stop Win £</Label>
            <Input data-testid="input-stop-win" type="number" step="0.01"
              value={form.stop_win} onChange={(e) => update("stop_win", e.target.value)}
              className={inputCls} />
          </div>
          <div className="space-y-1.5">
            <Label className="label-xs">Stop Loss £</Label>
            <Input data-testid="input-stop-loss" type="number" step="0.01"
              value={form.stop_loss} onChange={(e) => update("stop_loss", e.target.value)}
              className={inputCls} />
          </div>
          <div className="space-y-1.5 col-span-2">
            <Label className="label-xs">Max Races / Day</Label>
            <Input data-testid="input-max-races" type="number" min="1" max="200"
              value={form.max_races} onChange={(e) => update("max_races", e.target.value)}
              className={inputCls} />
          </div>
          <div className="space-y-1.5 col-span-2">
            <Label className="label-xs">Betfair Commission %</Label>
            <div className="grid grid-cols-5 gap-1.5">
              {[0, 0.02, 0.05, 0.065, 0.10].map((c) => {
                const active = Math.abs((form.commission_rate ?? 0.05) - c) < 0.001;
                return (
                  <button key={c} type="button"
                    data-testid={`commission-${(c*100).toFixed(1)}`}
                    onClick={() => update("commission_rate", c)}
                    className={`p-2 border font-mono text-sm transition-colors ${
                      active ? "border-pink-500 bg-pink-500/10 text-pink-400 font-bold"
                             : "border-[#2A2A2A] hover:bg-[#1C1C1C] text-zinc-400"
                    }`}>
                    {(c * 100).toFixed(c === 0.065 ? 1 : 0)}%
                  </button>
                );
              })}
            </div>
            <div className="text-[10px] text-zinc-500 font-mono">
              Default 5% = standard Betfair UK. 0% for pre-commission simulation.
            </div>
          </div>
          <div className="space-y-1.5 col-span-2">
            <Label className="label-xs">Max Liability Cap £ (bust protection)</Label>
            <Input data-testid="input-max-liability-cap" type="number" step="0.01" min="0"
              value={form.max_liability_cap}
              onChange={(e) => update("max_liability_cap", e.target.value)}
              className={inputCls} />
            <div className="text-[10px] text-zinc-500 font-mono">
              Any recovery bet whose liability would exceed this auto-busts the chain. Set 0 to disable.
            </div>
          </div>
          <div className="space-y-1.5 col-span-2">
            <Label className="label-xs">Recovery Levels (depth of staircase)</Label>
            <div className="grid grid-cols-5 gap-1.5">
              {[1, 2, 3, 4, 5].map((n) => {
                const active = parseInt(form.max_recovery_level) === n;
                return (
                  <button key={n} type="button"
                    data-testid={`recovery-level-${n}`}
                    onClick={() => update("max_recovery_level", n)}
                    className={`p-2 border font-mono text-sm transition-colors ${
                      active ? "border-pink-500 bg-pink-500/10 text-pink-400 font-bold"
                             : "border-[#2A2A2A] hover:bg-[#1C1C1C] text-zinc-400"
                    }`}>L{n}</button>
                );
              })}
            </div>
            <div className="text-[10px] text-zinc-500 font-mono">
              Chain busts after L{form.max_recovery_level} loss. Higher = more recovery attempts but bigger drawdowns.
            </div>
          </div>
          <div className="space-y-1.5 col-span-2">
            <Label className="label-xs">Lay Odds Range (skip favs outside this band)</Label>
            <div className="grid grid-cols-2 gap-2">
              <Input data-testid="input-odds-min" type="number" step="0.01" min="1.01"
                value={form.odds_min} onChange={(e) => update("odds_min", e.target.value)}
                placeholder="min e.g. 2.00" className={inputCls} />
              <Input data-testid="input-odds-max" type="number" step="0.01" min="1.01"
                value={form.odds_max} onChange={(e) => update("odds_max", e.target.value)}
                placeholder="max e.g. 4.00" className={inputCls} />
            </div>
            <div className="text-[10px] text-zinc-500 font-mono">
              Lay only when favourite odds fall in [{form.odds_min}, {form.odds_max}]. Tighter band = fewer bets but typically better EV.
            </div>
          </div>
        </div>

        <CapPreview
          stake={form.stake}
          maxLiabilityCap={form.max_liability_cap}
          numFavourites={form.num_favourites}
          commissionRate={form.commission_rate}
          oddsMin={form.odds_min}
          oddsMax={form.odds_max}
          maxRecoveryLevel={form.max_recovery_level}
        />

        {form.mode === "live" && (
          <div className="space-y-3 pt-2 border-t border-red-500/30">
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-4 h-4" />
              <div className="font-display uppercase text-sm font-bold">Live Mode Warning</div>
            </div>
            <div className="flex items-start gap-2 p-3 bg-red-500/5 border border-red-500/30">
              <Checkbox
                data-testid="risk-accept-checkbox"
                id="risk"
                checked={form.risk_accepted}
                onCheckedChange={(v) => update("risk_accepted", !!v)}
                className="mt-0.5 rounded-none border-red-500/50 data-[state=checked]:bg-red-600"
              />
              <label htmlFor="risk" className="text-xs leading-relaxed cursor-pointer">
                I accept that real lay bets will be placed on my Betfair account and real money is at risk.
                I understand the recovery system can lose money and agree to use a max liability cap.
              </label>
            </div>

            {/* Auto-place toggle */}
            <div className="flex items-start justify-between gap-3 p-3 bg-[#141414] border border-[#2A2A2A]" data-testid="auto-place-row">
              <div>
                <div className="font-display font-bold text-sm uppercase tracking-wider text-white">
                  Auto-place bets
                </div>
                <div className="text-[11px] text-zinc-500 leading-relaxed mt-1 max-w-md">
                  Automatically fire the lay bets <span className="text-pink-400 font-bold">60 seconds before</span> each
                  upcoming UK greyhound race. Leave OFF to place each race manually.
                </div>
              </div>
              <Switch
                data-testid="auto-place-switch"
                checked={form.auto_place}
                onCheckedChange={(v) => update("auto_place", !!v)}
                className="data-[state=checked]:bg-pink-500"
              />
            </div>

            <div className="p-3 bg-[#141414] border border-[#2A2A2A] space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-display font-bold text-sm uppercase tracking-wider text-white">
                    Chase unmatched lays
                  </div>
                  <div className="text-[11px] text-zinc-500 leading-relaxed mt-1 max-w-md">
                    If a live lay is fully unmatched, cancel it and retry one Betfair tick higher until matched, timed out, or capped.
                  </div>
                </div>
                <Switch
                  data-testid="price-chase-switch"
                  checked={form.live_price_chase}
                  onCheckedChange={(v) => update("live_price_chase", !!v)}
                  className="data-[state=checked]:bg-pink-500"
                />
              </div>
              {form.live_price_chase && (
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1.5">
                    <Label className="label-xs">Max chase ticks</Label>
                    <Input
                      data-testid="input-price-chase-ticks"
                      type="number"
                      min="0"
                      max="25"
                      value={form.live_price_chase_ticks}
                      onChange={(e) => update("live_price_chase_ticks", e.target.value)}
                      className={inputCls}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="label-xs">Max chase seconds</Label>
                    <Input
                      data-testid="input-price-chase-seconds"
                      type="number"
                      min="1"
                      max="60"
                      value={form.live_price_chase_seconds}
                      onChange={(e) => update("live_price_chase_seconds", e.target.value)}
                      className={inputCls}
                    />
                  </div>
                </div>
              )}
              <div className="text-[10px] text-amber-300/80 font-mono">
                Guarded by Odds Max and Max Liability Cap. The app will not chase beyond either limit.
              </div>
            </div>

            {/* Small-bet info — sub-£1 lays use Betfair betTargetType=BACKERS_PROFIT */}
            <div className="bg-amber-500/5 border border-amber-500/30 px-3 py-2">
              <div className="text-xs font-display uppercase tracking-wider text-amber-300 font-bold">
                Sub-£1 lay support
              </div>
              <div className="text-[11px] text-zinc-400 leading-relaxed mt-1 max-w-xl">
                Stakes below Betfair's £1 minimum (e.g. <span className="text-amber-300 font-bold">£0.05 or £0.50</span>)
                are placed automatically using Betfair's <span className="text-amber-300">BACKERS_PROFIT</span> liability
                targeting. <span className="text-amber-300">Works transparently for every L0–L5 bet — no parked orders, no residue.</span>
              </div>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button data-testid="cancel-session-btn" variant="ghost" onClick={() => setOpen(false)}
            className="rounded-none text-zinc-400 hover:text-white hover:bg-[#1C1C1C]">
            Cancel
          </Button>
          <Button data-testid="create-session-btn" onClick={submit}
            disabled={loading || !canSubmit()}
            className="bg-pink-600 hover:bg-pink-500 text-white font-bold uppercase tracking-wider rounded-none disabled:opacity-40">
            {loading ? "Creating…" : "Start Session"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
