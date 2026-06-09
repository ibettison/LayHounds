import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Key, ShieldCheck, ShieldAlert, ShieldX, RefreshCw, Copy, ExternalLink } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { API } from "../lib/api";

const fmtDate = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
};

export const LicencePanel = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [key, setKey] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/licence/status`);
      setData(r.data);
    } catch (e) {
      // 404 means the licence module is not wired on this install — silently hide the panel.
      if (e.response?.status !== 404) {
        toast.error(e.response?.data?.detail || "Could not read licence status");
      }
      setData(null);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const activate = async () => {
    if (!key.trim()) return toast.error("Paste your licence key first");
    setLoading(true);
    try {
      const r = await axios.post(`${API}/licence/activate`, { key: key.trim(), install_id: data?.install_id || "" });
      setData(r.data);
      setKey("");
      if (r.data.ok) toast.success("Licence activated — Paper-Live & Live unlocked");
      else toast.warning(r.data.message || "Activation completed but not yet usable");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Activation failed");
    } finally {
      setLoading(false);
    }
  };

  const release = async () => {
    setLoading(true);
    try {
      const r = await axios.post(`${API}/licence/release`);
      setData(r.data);
      toast.success("Licence released. You can now activate it on another install.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Release failed");
    } finally {
      setLoading(false);
    }
  };

  const refresh = async () => {
    setLoading(true);
    try {
      const r = await axios.post(`${API}/licence/refresh`);
      setData(r.data);
      if (r.data.ok) toast.success("Licence re-validated");
      else toast.warning(r.data.message || "Licence not valid");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Refresh failed");
    } finally {
      setLoading(false);
    }
  };

  const copyInstallId = () => {
    if (!data?.install_id) return;
    navigator.clipboard?.writeText(data.install_id).then(() => toast.success("Install ID copied"));
  };

  if (!data) return null;  // module not wired

  const isActive = data.ok && data.bound;
  const Icon = isActive ? ShieldCheck : data.has_key ? ShieldAlert : ShieldX;
  const headTone = isActive ? "text-emerald-400" : data.has_key ? "text-amber-400" : "text-zinc-500";

  return (
    <div className="border border-[#2A2A2A] bg-[#141414]" data-testid="licence-panel">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#2A2A2A]">
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${headTone}`} />
          <span className="font-display font-bold text-sm uppercase tracking-wider text-white">
            Live Unlock Licence
          </span>
        </div>
        {data.has_key && (
          <Button
            data-testid="licence-refresh"
            variant="ghost" size="sm" onClick={refresh} disabled={loading}
            className="text-zinc-400 hover:text-pink-400 h-7 px-2"
            title="Force re-validate now"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
          </Button>
        )}
      </div>

      <div className="p-4 space-y-3">
        {data.has_key ? (
          <>
            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div>
                <div className="text-[9px] uppercase tracking-widest text-zinc-500">Status</div>
                <div className={`font-bold mt-0.5 ${isActive ? "text-emerald-400" : "text-amber-400"}`}>
                  {isActive ? "ACTIVE" : (data.status || "INACTIVE").toUpperCase()}
                </div>
              </div>
              <div>
                <div className="text-[9px] uppercase tracking-widest text-zinc-500">Key</div>
                <div className="text-white mt-0.5">{data.licence_key_masked}</div>
              </div>
              <div>
                <div className="text-[9px] uppercase tracking-widest text-zinc-500">Renews / Ends</div>
                <div className="text-white mt-0.5">{fmtDate(data.current_period_end)}</div>
              </div>
              <div>
                <div className="text-[9px] uppercase tracking-widest text-zinc-500">Last Validated</div>
                <div className="text-white mt-0.5">{fmtDate(data.last_validation_at)}</div>
              </div>
            </div>

            {data.message && (
              <div className="text-[11px] text-amber-400 font-mono bg-amber-500/5 border border-amber-500/20 px-2 py-1.5">
                {data.message}
              </div>
            )}

            <Button
              data-testid="licence-release"
              onClick={release} disabled={loading}
              variant="outline"
              className="w-full rounded-none border-[#2A2A2A] text-zinc-400 hover:text-red-400 hover:border-red-500/40 hover:bg-red-500/10 font-bold uppercase tracking-wider text-xs"
            >
              Release this install
            </Button>
          </>
        ) : (
          <>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Paste the licence key you received after purchase to unlock Paper-Live & Live modes.
            </p>
            <div className="flex gap-2">
              <Input
                data-testid="licence-key-input"
                placeholder="LH-XXXX-XXXX-XXXX-XXXX"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && activate()}
                className="rounded-none bg-[#0A0A0A] border-[#2A2A2A] text-white placeholder:text-zinc-600 font-mono"
              />
              <Button
                data-testid="licence-activate"
                onClick={activate} disabled={loading}
                className="rounded-none bg-pink-500 hover:bg-pink-600 text-white font-bold uppercase tracking-wider text-xs"
              >
                <Key className="w-3 h-3 mr-1" /> Activate
              </Button>
            </div>
          </>
        )}

        <div className="pt-2 border-t border-[#2A2A2A] flex items-center justify-between text-[10px] font-mono text-zinc-500">
          <span>Install ID</span>
          <button
            data-testid="licence-install-id"
            onClick={copyInstallId}
            className="flex items-center gap-1 text-zinc-400 hover:text-pink-400"
          >
            {data.install_id?.slice(0, 13)}…
            <Copy className="w-2.5 h-2.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
