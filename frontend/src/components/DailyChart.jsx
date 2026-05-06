import React, { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Bar, BarChart, ReferenceLine } from "recharts";
import { api } from "../lib/api";
import { TrendingUp, TrendingDown } from "lucide-react";

const fmtDate = (iso) => {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" }) +
           " " + d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
};

const TooltipBox = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="bg-[#0A0A0A] border border-[#2A2A2A] p-3 font-mono text-xs">
      <div className="label-xs mb-1">{fmtDate(row.created_at)}</div>
      <div className="flex gap-2">
        <span className="text-zinc-500">P&L:</span>
        <span className={row.pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
          {row.pnl >= 0 ? "+" : ""}£{row.pnl.toFixed(2)}
        </span>
      </div>
      <div className="flex gap-2">
        <span className="text-zinc-500">Cumulative:</span>
        <span className={row.cumulative_pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
          {row.cumulative_pnl >= 0 ? "+" : ""}£{row.cumulative_pnl.toFixed(2)}
        </span>
      </div>
      <div className="flex gap-2">
        <span className="text-zinc-500">Bank end:</span>
        <span className="text-white">£{row.bank_end.toFixed(2)}</span>
      </div>
      <div className="flex gap-2">
        <span className="text-zinc-500">Races:</span>
        <span className="text-white">{row.races}</span>
      </div>
    </div>
  );
};

export const DailyChart = ({ refreshKey }) => {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.dailyStats().then(setData).catch(() => setData({ days: [], total_pnl: 0, sessions: 0 }));
  }, [refreshKey]);

  if (!data) {
    return <div className="bg-[#141414] border border-[#2A2A2A] p-6 text-zinc-500">Loading…</div>;
  }

  const days = data.days.map((d, i) => ({ ...d, idx: i + 1 }));
  const wins = days.filter((d) => d.pnl > 0).length;
  const losses = days.filter((d) => d.pnl < 0).length;
  const winRate = days.length ? ((wins / days.length) * 100).toFixed(0) : "0";

  return (
    <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="daily-chart-panel">
      <div className="bg-[#0A0A0A] border-b border-[#2A2A2A] p-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="label-xs">Trading Journal</div>
          <div className="font-display text-xl uppercase tracking-tight">
            Daily P&amp;L — {data.sessions} {data.sessions === 1 ? "day" : "days"}
          </div>
        </div>
        <div className="flex items-center gap-5 text-sm font-mono">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <span className="text-emerald-400">{wins}W</span>
          </div>
          <div className="flex items-center gap-2">
            <TrendingDown className="w-4 h-4 text-red-400" />
            <span className="text-red-400">{losses}L</span>
          </div>
          <div className="label-xs">Win {winRate}%</div>
          <div
            className={`font-bold text-lg ${
              data.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"
            }`}
            data-testid="total-pnl-all-time"
          >
            {data.total_pnl >= 0 ? "+" : ""}£{data.total_pnl.toFixed(2)}
          </div>
        </div>
      </div>

      {days.length === 0 ? (
        <div className="p-10 text-center text-zinc-500 text-sm">
          No completed sessions yet. Start a session and run some races.
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 p-4">
          {/* Cumulative line */}
          <div>
            <div className="label-xs mb-2">Cumulative P&amp;L</div>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={days} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid stroke="#2A2A2A" strokeDasharray="2 4" vertical={false} />
                <XAxis dataKey="idx" stroke="#52525B" fontSize={11} tickLine={false} axisLine={{ stroke: "#2A2A2A" }} />
                <YAxis stroke="#52525B" fontSize={11} tickLine={false} axisLine={{ stroke: "#2A2A2A" }} tickFormatter={(v) => `£${v}`} />
                <Tooltip content={<TooltipBox />} cursor={{ stroke: "#EC4899", strokeDasharray: "3 3" }} />
                <ReferenceLine y={0} stroke="#52525B" strokeDasharray="2 2" />
                <Line
                  type="monotone"
                  dataKey="cumulative_pnl"
                  stroke="#EC4899"
                  strokeWidth={2}
                  dot={{ fill: "#EC4899", r: 3 }}
                  activeDot={{ r: 5 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Daily P&L bars */}
          <div>
            <div className="label-xs mb-2">P&amp;L per Session</div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={days} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid stroke="#2A2A2A" strokeDasharray="2 4" vertical={false} />
                <XAxis dataKey="idx" stroke="#52525B" fontSize={11} tickLine={false} axisLine={{ stroke: "#2A2A2A" }} />
                <YAxis stroke="#52525B" fontSize={11} tickLine={false} axisLine={{ stroke: "#2A2A2A" }} tickFormatter={(v) => `£${v}`} />
                <Tooltip content={<TooltipBox />} cursor={{ fill: "#1C1C1C" }} />
                <ReferenceLine y={0} stroke="#52525B" />
                <Bar dataKey="pnl" isAnimationActive={false}
                  shape={(props) => {
                    const { x, y, width, height, payload } = props;
                    const fill = payload.pnl >= 0 ? "#10B981" : "#EF4444";
                    // Recharts can emit negative height for negative values; normalise
                    const h = Math.abs(height);
                    const yy = height < 0 ? y + height : y;
                    return <rect x={x} y={yy} width={width} height={h} fill={fill} />;
                  }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
};
