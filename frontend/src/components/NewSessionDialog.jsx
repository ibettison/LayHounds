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
import { Plus, AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

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
            <Label className="label-xs">Starting Bank £</Label>
            <Input data-testid="input-starting-bank" type="number" step="0.01"
              value={form.starting_bank} onChange={(e) => update("starting_bank", e.target.value)}
              className={inputCls} />
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
        </div>

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
