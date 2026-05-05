import React from "react";
import { Trash2 } from "lucide-react";
import { Button } from "../components/ui/button";

export const SessionList = ({ sessions, currentId, onSelect, onDelete }) => {
  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="session-list-panel">
      <div className="bg-[#0A0A0A] border-b border-[#2A2A2A] p-4">
        <div className="label-xs">Archive</div>
        <div className="font-display text-xl uppercase tracking-tight">Sessions</div>
      </div>
      <div className="max-h-[300px] overflow-y-auto">
        {sessions.length === 0 && (
          <div className="p-6 text-center text-zinc-500 text-sm">No sessions yet.</div>
        )}
        {sessions.map((s) => {
          const active = s.id === currentId;
          return (
            <div
              key={s.id}
              data-testid={`session-item-${s.id}`}
              className={`border-b border-[#2A2A2A] p-3 cursor-pointer transition-colors flex items-center justify-between gap-2 ${
                active ? "bg-pink-500/10 border-l-2 border-l-pink-500" : "hover:bg-[#1C1C1C]/50"
              }`}
              onClick={() => onSelect(s.id)}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="label-xs">{s.status.replace("_", " ")}</span>
                  <span className="text-xs text-zinc-500 font-mono">
                    {s.races_played}/{s.config.max_races}r
                  </span>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <span
                    className={`font-mono font-bold ${
                      s.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {s.total_pnl >= 0 ? "+" : ""}£{s.total_pnl.toFixed(2)}
                  </span>
                  <span className="text-zinc-500 text-xs font-mono">
                    bank £{s.bank.toFixed(2)}
                  </span>
                </div>
              </div>
              <Button
                data-testid={`delete-session-${s.id}`}
                variant="ghost"
                size="sm"
                className="rounded-none h-7 w-7 p-0 text-zinc-500 hover:text-red-400 hover:bg-red-500/10"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(s.id);
                }}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
};
