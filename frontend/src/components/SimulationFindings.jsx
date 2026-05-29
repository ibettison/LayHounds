import React from "react";
import { BarChart3 } from "lucide-react";

const headlineRows = [
  {
    label: "Best small-stake balance",
    config: "Bank \u00a310-\u00a325 / stake \u00a30.05 / cap \u00a310 / 20 races",
    avg: "\u00a30.36-\u00a30.41",
    positive: "75%",
    drawdown: "\u00a36.01-\u00a36.43",
  },
  {
    label: "Lower drawdown option",
    config: "Bank \u00a325-\u00a350 / stake \u00a30.05 / cap \u00a35 / 20 races",
    avg: "\u00a30.37-\u00a30.38",
    positive: "70%",
    drawdown: "\u00a35.42-\u00a35.54",
  },
  {
    label: "Higher stake, higher swing",
    config: "Bank \u00a325-\u00a350 / stake \u00a30.10 / cap \u00a310 / 20 races",
    avg: "\u00a30.63-\u00a30.67",
    positive: "69-70%",
    drawdown: "\u00a311.07-\u00a311.43",
  },
];

export const SimulationFindings = () => (
  <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="simulation-findings">
    <div className="flex items-center justify-between gap-3 bg-[#0A0A0A] border-b border-[#2A2A2A] p-4">
      <div>
        <div className="label-xs">Monte Carlo Findings</div>
        <div className="font-display text-2xl uppercase tracking-tight">
          Simulator configuration sweep
        </div>
      </div>
      <div className="w-10 h-10 bg-pink-600/15 border border-pink-500/30 grid place-items-center">
        <BarChart3 className="w-5 h-5 text-pink-300" />
      </div>
    </div>

    <div className="p-4 space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <FindingStat label="Broad sweep" value="12,150" sub="simulated days" />
        <FindingStat label="Deep rerun" value="24,000" sub="leading setups" />
        <FindingStat label="Commission" value="5%" sub="fixed" />
        <FindingStat label="Best hit-rate" value="75%" sub="positive days" />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px]">
          <thead>
            <tr className="text-xs uppercase tracking-wider text-zinc-500 border-b border-[#2A2A2A]">
              <th className="py-2 text-left">Finding</th>
              <th className="py-2 text-left">Configuration</th>
              <th className="py-2 text-right">Avg P&amp;L</th>
              <th className="py-2 text-right">Positive</th>
              <th className="py-2 text-right">95% Drawdown</th>
            </tr>
          </thead>
          <tbody>
            {headlineRows.map((row) => (
              <tr key={row.label} className="border-b border-[#2A2A2A]/70">
                <td className="py-3 pr-3 font-bold text-sm text-white">{row.label}</td>
                <td className="py-3 pr-3 text-sm text-zinc-400 font-mono">{row.config}</td>
                <td className="py-3 pr-3 text-right text-emerald-400 font-mono">{row.avg}</td>
                <td className="py-3 pr-3 text-right text-zinc-300 font-mono">{row.positive}</td>
                <td className="py-3 text-right text-amber-300 font-mono">{row.drawdown}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid md:grid-cols-3 gap-3 text-sm">
        <Note
          title="Most favourable practical setup"
          body="The strongest repeatable area was 20 races, \u00a30.05 stake, two favourites, and a \u00a35-\u00a310 liability cap. \u00a310 cap gave the best hit-rate; \u00a35 reduced the bad tail."
        />
        <Note
          title="Why GBP2.00 is not guaranteed"
          body="The theoretical 20-race target is about \u00a31.90 after commission, but recovery chains can be capped or bust before catching up. The median small-stake result was close to target, while the average was pulled down by loss clusters."
        />
        <Note
          title="Bank sizing"
          body="A \u00a310 bank fitted most \u00a30.05 runs, but the 5% tail reached around \u00a36 drawdown and rare worse runs exceeded \u00a310. \u00a325+ is much calmer for the same stake."
        />
      </div>
    </div>
  </div>
);

const FindingStat = ({ label, value, sub }) => (
  <div className="bg-[#0A0A0A] border border-[#2A2A2A] p-3">
    <div className="label-xs mb-1">{label}</div>
    <div className="font-mono text-xl font-bold text-white">{value}</div>
    <div className="text-xs text-zinc-500 font-mono">{sub}</div>
  </div>
);

const Note = ({ title, body }) => (
  <div className="bg-[#0A0A0A] border border-[#2A2A2A] p-3">
    <div className="font-display uppercase tracking-tight text-lg mb-1">{title}</div>
    <div className="text-zinc-400 leading-relaxed">{body}</div>
  </div>
);
