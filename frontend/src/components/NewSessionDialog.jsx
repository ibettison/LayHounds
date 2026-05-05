import React, { useState } from "react";
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
import { Plus } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

export const NewSessionDialog = ({ onCreated }) => {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    starting_bank: 10,
    num_favourites: 2,
    stop_win: 5,
    stop_loss: 5,
    max_races: 20,
  });

  const update = (k, v) => setForm((p) => ({ ...p, [k]: v }));

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
      });
      toast.success(`Session created`);
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
        className="bg-[#141414] border-[#2A2A2A] rounded-none text-white max-w-md"
      >
        <DialogHeader>
          <DialogTitle className="font-display uppercase text-2xl tracking-tight">
            New Session
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            Configure your lay-betting strategy. Stake is fixed at £0.05.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-4 py-2">
          <div className="space-y-1.5">
            <Label className="label-xs">Starting Bank £</Label>
            <Input
              data-testid="input-starting-bank"
              type="number"
              step="0.01"
              value={form.starting_bank}
              onChange={(e) => update("starting_bank", e.target.value)}
              className={inputCls}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="label-xs"># Favourites</Label>
            <Input
              data-testid="input-num-favourites"
              type="number"
              min="1"
              max="4"
              value={form.num_favourites}
              onChange={(e) => update("num_favourites", e.target.value)}
              className={inputCls}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="label-xs">Stop Win £</Label>
            <Input
              data-testid="input-stop-win"
              type="number"
              step="0.01"
              value={form.stop_win}
              onChange={(e) => update("stop_win", e.target.value)}
              className={inputCls}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="label-xs">Stop Loss £</Label>
            <Input
              data-testid="input-stop-loss"
              type="number"
              step="0.01"
              value={form.stop_loss}
              onChange={(e) => update("stop_loss", e.target.value)}
              className={inputCls}
            />
          </div>
          <div className="space-y-1.5 col-span-2">
            <Label className="label-xs">Max Races / Day</Label>
            <Input
              data-testid="input-max-races"
              type="number"
              min="1"
              max="200"
              value={form.max_races}
              onChange={(e) => update("max_races", e.target.value)}
              className={inputCls}
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            data-testid="cancel-session-btn"
            variant="ghost"
            onClick={() => setOpen(false)}
            className="rounded-none text-zinc-400 hover:text-white hover:bg-[#1C1C1C]"
          >
            Cancel
          </Button>
          <Button
            data-testid="create-session-btn"
            onClick={submit}
            disabled={loading}
            className="bg-pink-600 hover:bg-pink-500 text-white font-bold uppercase tracking-wider rounded-none"
          >
            {loading ? "Creating…" : "Start Session"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
