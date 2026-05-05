import React, { useEffect, useState } from "react";
import { Wifi, WifiOff, Loader2 } from "lucide-react";
import { api } from "../lib/api";

export const BetfairStatusBadge = () => {
  const [status, setStatus] = useState({ loading: true });

  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        const s = await api.betfairStatus();
        if (mounted) setStatus({ ...s, loading: false });
      } catch (e) {
        if (mounted) setStatus({ loading: false, error: e.message });
      }
    };
    poll();
    const iv = setInterval(poll, 30000);
    return () => {
      mounted = false;
      clearInterval(iv);
    };
  }, []);

  if (status.loading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 border border-[#2A2A2A] bg-[#141414] text-zinc-500">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        <span className="label-xs">Betfair</span>
      </div>
    );
  }

  const connected = status.configured && status.logged_in;
  const geoBlocked = status.reason?.includes("GEO_BLOCKED") || status.reason?.includes("blocked region");

  let tone, Icon, label, detail;
  if (connected) {
    tone = "text-emerald-400 border-emerald-500/30 bg-emerald-500/10";
    Icon = Wifi;
    label = "Betfair Live";
    detail = `key …${status.app_key_tail}`;
  } else if (geoBlocked) {
    tone = "text-amber-400 border-amber-500/30 bg-amber-500/10";
    Icon = WifiOff;
    label = "Geo-Blocked";
    detail = "deploy UK/EU";
  } else if (!status.configured) {
    tone = "text-zinc-500 border-[#2A2A2A] bg-[#141414]";
    Icon = WifiOff;
    label = "No Creds";
    detail = "simulator only";
  } else {
    tone = "text-red-400 border-red-500/30 bg-red-500/10";
    Icon = WifiOff;
    label = "Offline";
    detail = status.reason?.slice(0, 40) || "";
  }

  return (
    <div
      data-testid="betfair-status-badge"
      title={status.reason || ""}
      className={`flex items-center gap-2 px-3 py-1.5 border ${tone}`}
    >
      <Icon className="w-3.5 h-3.5" />
      <div className="leading-tight">
        <div className="text-xs font-bold uppercase tracking-wider">{label}</div>
        {detail && <div className="text-[10px] text-zinc-500 font-mono">{detail}</div>}
      </div>
    </div>
  );
};
