import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Filter,
  KeyRound,
  Server,
  ShieldAlert,
  Signal,
  WifiOff,
  X,
} from "lucide-react";
import { api } from "@/lib/api";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "online", label: "Online" },
  { id: "offline", label: "Offline" },
  { id: "errors", label: "Errors" },
  { id: "live", label: "Live mode" },
  { id: "paper", label: "Paper mode" },
  { id: "old", label: "Old version" },
];

const statusStyles = {
  Online: "border-emerald-300 bg-emerald-50 text-emerald-700",
  Offline: "border-zinc-300 bg-zinc-100 text-zinc-700",
  Warning: "border-amber-300 bg-amber-50 text-amber-700",
  Error: "border-red-300 bg-red-50 text-red-700",
};

function formatAgo(value) {
  if (!value) return "Never";
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "Unknown";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds} seconds ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  return `${days} days ago`;
}

function money(value) {
  if (value === null || value === undefined || value === "") return "-";
  return `GBP ${Number(value || 0).toFixed(2)}`;
}

function short(value) {
  return value || "-";
}

function installMatchesFilter(install, filter) {
  if (filter === "online") return install.online;
  if (filter === "offline") return !install.online;
  if (filter === "errors") return install.status_badge === "Error" || Boolean(install.last_error_code);
  if (filter === "live") return install.environment === "live";
  if (filter === "paper") return ["paper", "paper-live", "simulator"].includes(install.environment);
  if (filter === "old") return install.old_version;
  return true;
}

function SummaryCard({ icon: Icon, label, value, tone = "zinc" }) {
  const tones = {
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    red: "border-red-200 bg-red-50 text-red-700",
    zinc: "border-zinc-200 bg-white text-zinc-800",
  };
  return (
    <div className={`rounded-lg border p-4 ${tones[tone]}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium">{label}</div>
        <Icon className="h-4 w-4" />
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-normal">{value ?? 0}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-semibold ${statusStyles[status] || statusStyles.Offline}`}>
      {status}
    </span>
  );
}

function DetailRow({ label, value }) {
  return (
    <div className="grid grid-cols-[160px_1fr] gap-3 border-b border-zinc-100 py-2 text-sm">
      <div className="text-zinc-500">{label}</div>
      <div className="min-w-0 break-words font-medium text-zinc-900">{value ?? "-"}</div>
    </div>
  );
}

function DetailsDrawer({ install, onClose, latestVersion }) {
  if (!install) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/25" onClick={onClose}>
      <aside
        className="h-full w-full max-w-xl overflow-y-auto bg-white p-6 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-normal text-zinc-500">Install details</div>
            <h2 className="mt-1 text-xl font-semibold text-zinc-950">{install.install_id}</h2>
          </div>
          <button className="rounded-md border border-zinc-200 p-2 text-zinc-600 hover:bg-zinc-50" onClick={onClose} aria-label="Close details">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <StatusBadge status={install.status_badge} />
          {install.old_version && <span className="rounded-full border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700">Old version</span>}
          {install.betfair_connected === false && <span className="rounded-full border border-red-300 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700">Betfair disconnected</span>}
          {install.licence_validation_status === "failing" && <span className="rounded-full border border-red-300 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700">Licence failing</span>}
        </div>

        <section className="mt-6">
          <h3 className="text-sm font-semibold text-zinc-950">App and deployment</h3>
          <div className="mt-2">
            <DetailRow label="App version" value={install.app_version} />
            <DetailRow label="Latest version" value={latestVersion || "-"} />
            <DetailRow label="Backend version" value={install.backend_version || install.git_commit} />
            <DetailRow label="Environment" value={install.environment} />
            <DetailRow label="Recovery mode" value={install.recovery_mode} />
            <DetailRow label="Strategy profile" value={install.strategy_profile} />
          </div>
        </section>

        <section className="mt-6">
          <h3 className="text-sm font-semibold text-zinc-950">Health and session</h3>
          <div className="mt-2">
            <DetailRow label="Backend status" value={install.backend_status} />
            <DetailRow label="Betfair connected" value={String(Boolean(install.betfair_connected))} />
            <DetailRow label="Licence validation" value={install.licence_validation_status} />
            <DetailRow label="Last error code" value={install.last_error_code} />
            <DetailRow label="Last error message" value={install.last_error_message} />
            <DetailRow label="Last error at" value={install.last_error_at} />
            <DetailRow label="Current mode" value={install.current_mode} />
            <DetailRow label="Session running" value={String(Boolean(install.session_running))} />
            <DetailRow label="Sessions today" value={install.sessions_today ?? install.sessions_started_today ?? 0} />
            <DetailRow label="Last session result" value={install.last_session_result} />
          </div>
        </section>

        <section className="mt-6">
          <h3 className="text-sm font-semibold text-zinc-950">Recovery safety</h3>
          <div className="mt-2">
            <DetailRow label="Current debt" value={money(install.current_recovery_debt)} />
            <DetailRow label="Max debt today" value={money(install.max_recovery_debt_today)} />
            <DetailRow label="Liability cap" value={money(install.current_liability_cap)} />
            <DetailRow label="Max liability today" value={money(install.max_liability_used_today)} />
            <DetailRow label="Stop win" value={money(install.stop_win)} />
            <DetailRow label="Stop loss" value={money(install.stop_loss)} />
          </div>
        </section>

        <section className="mt-6">
          <h3 className="text-sm font-semibold text-zinc-950">Alert rules</h3>
          <div className="mt-2 space-y-2">
            {(install.alerts || []).length === 0 ? (
              <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-600">No active alerts</div>
            ) : (
              install.alerts.map((alert) => (
                <div key={alert.code} className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                  <div className="font-semibold">{alert.message}</div>
                  <div className="text-xs uppercase tracking-normal">{alert.code}</div>
                </div>
              ))
            )}
          </div>
        </section>
      </aside>
    </div>
  );
}

export default function Admin() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let live = true;
    async function load() {
      try {
        const result = await api.adminOperations();
        if (live) {
          setData(result);
          setError("");
        }
      } catch (err) {
        if (live) setError(err.response?.data?.detail || err.message || "Could not load Operations Dashboard");
      } finally {
        if (live) setLoading(false);
      }
    }
    load();
    const timer = setInterval(load, 30000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, []);

  const filtered = useMemo(
    () => (data?.installs || []).filter((install) => installMatchesFilter(install, filter)),
    [data?.installs, filter],
  );
  const summary = data?.summary || {};

  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950">
      <div className="mx-auto max-w-7xl px-5 py-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-normal text-zinc-500">Admin</div>
            <h1 className="mt-1 text-3xl font-semibold tracking-normal">Operations Dashboard v2</h1>
          </div>
          <div className="text-sm text-zinc-500">
            Latest app version: <span className="font-semibold text-zinc-800">{data?.latest_app_version || "unknown"}</span>
          </div>
        </div>

        {error && (
          <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <SummaryCard icon={Signal} label="Online now" value={summary.online_now} tone="emerald" />
          <SummaryCard icon={Activity} label="Active today" value={summary.active_today} />
          <SummaryCard icon={CheckCircle2} label="Live mode running" value={summary.live_mode_running} tone="emerald" />
          <SummaryCard icon={WifiOff} label="Betfair errors" value={summary.betfair_errors} tone="red" />
          <SummaryCard icon={AlertTriangle} label="Old versions" value={summary.old_versions} tone="amber" />
          <SummaryCard icon={ShieldAlert} label="Licence failures" value={summary.licence_failures} tone="red" />
        </div>

        <div className="mt-6 rounded-lg border border-zinc-200 bg-white">
          <div className="flex flex-col gap-3 border-b border-zinc-200 p-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold text-zinc-800">
              <Filter className="h-4 w-4" />
              Filters
            </div>
            <div className="flex flex-wrap gap-2">
              {FILTERS.map((item) => (
                <button
                  key={item.id}
                  className={`rounded-md border px-3 py-2 text-sm font-medium ${
                    filter === item.id
                      ? "border-zinc-950 bg-zinc-950 text-white"
                      : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
                  }`}
                  onClick={() => setFilter(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-50 text-left text-xs font-semibold uppercase tracking-normal text-zinc-500">
                <tr>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Install</th>
                  <th className="px-4 py-3">Last seen ago</th>
                  <th className="px-4 py-3">Version</th>
                  <th className="px-4 py-3">Environment</th>
                  <th className="px-4 py-3">Betfair</th>
                  <th className="px-4 py-3">Licence</th>
                  <th className="px-4 py-3">Session</th>
                  <th className="px-4 py-3">Alerts</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {loading ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-zinc-500" colSpan={9}>Loading operations data...</td>
                  </tr>
                ) : filtered.length === 0 ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-zinc-500" colSpan={9}>No installs match this filter</td>
                  </tr>
                ) : (
                  filtered.map((install) => {
                    const flagged = install.licence_validation_status === "failing" || install.betfair_connected === false || install.old_version;
                    return (
                      <tr
                        key={install.install_id}
                        className={`cursor-pointer hover:bg-zinc-50 ${flagged ? "bg-amber-50/45" : "bg-white"}`}
                        onClick={() => setSelected(install)}
                      >
                        <td className="px-4 py-3"><StatusBadge status={install.status_badge} /></td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2 font-medium text-zinc-950">
                            <Server className="h-4 w-4 text-zinc-400" />
                            <span className="max-w-[220px] truncate">{install.install_id}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-zinc-700">
                          <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-zinc-400" />
                            {formatAgo(install.last_seen_at)}
                          </div>
                        </td>
                        <td className={`px-4 py-3 ${install.old_version ? "font-semibold text-amber-700" : "text-zinc-700"}`}>
                          {short(install.app_version)}
                        </td>
                        <td className="px-4 py-3 text-zinc-700">{short(install.environment)}</td>
                        <td className={`px-4 py-3 font-medium ${install.betfair_connected === false ? "text-red-700" : "text-emerald-700"}`}>
                          {install.betfair_connected ? "Connected" : "Disconnected"}
                        </td>
                        <td className={`px-4 py-3 font-medium ${install.licence_validation_status === "failing" ? "text-red-700" : "text-emerald-700"}`}>
                          <div className="flex items-center gap-2">
                            <KeyRound className="h-4 w-4 text-zinc-400" />
                            {short(install.licence_validation_status)}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-zinc-700">
                          {install.session_running ? "Running" : short(install.last_session_result)}
                        </td>
                        <td className="px-4 py-3 text-zinc-700">{(install.alerts || []).length}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <DetailsDrawer install={selected} onClose={() => setSelected(null)} latestVersion={data?.latest_app_version} />
    </main>
  );
}
