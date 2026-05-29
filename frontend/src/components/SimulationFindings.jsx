import React from "react";
import { BarChart3 } from "lucide-react";

const balancedRows = [
  {
    label: "Small stake",
    config: <>L5 / 4 favs / stake &pound;0.05 / cap &pound;100</>,
    day: <>&pound;1.53</>,
    week: <>&pound;7.66</>,
    month: <>&pound;30.65</>,
    risk: "95% positive / 4% bust",
  },
  {
    label: "Mid stake",
    config: <>L5 / 3 favs / stake &pound;0.50 / cap &pound;100</>,
    day: <>&pound;8.96</>,
    week: <>&pound;44.79</>,
    month: <>&pound;179.15</>,
    risk: "77% positive / 23% bust",
  },
  {
    label: "Large stake",
    config: <>L3 / 4 favs / stake &pound;1.00 / cap &pound;100</>,
    day: <>&pound;19.94</>,
    week: <>&pound;99.71</>,
    month: <>&pound;398.83</>,
    risk: "71% positive / 65% bust",
  },
];

const potentialRows = [
  {
    config: <>L5 / 2 favs / stake &pound;0.05 / cap &pound;100</>,
    month: <>&pound;15.79</>,
    drawdown: <>&pound;12.75</>,
    note: "Highest positive-day rate tested",
  },
  {
    config: <>L4 / 4 favs / stake &pound;0.50 / cap &pound;50</>,
    month: <>&pound;177.17</>,
    drawdown: <>&pound;60.53</>,
    note: "Similar upside with lower cap",
  },
  {
    config: <>L5 / 4 favs / stake &pound;1.00 / cap &pound;100</>,
    month: <>&pound;368.07</>,
    drawdown: <>&pound;114.60</>,
    note: "High upside, very wide swings",
  },
];

export const SimulationFindings = () => (
  <div className="bg-[#141414] border border-[#2A2A2A]" data-testid="simulation-findings">
    <div className="flex items-center justify-between gap-3 bg-[#0A0A0A] border-b border-[#2A2A2A] p-4">
      <div>
        <div className="label-xs">Monte Carlo Findings</div>
        <div className="font-display text-2xl uppercase tracking-tight">
          Stake sweep: &pound;0.05, &pound;0.50 and &pound;1.00
        </div>
      </div>
      <div className="w-10 h-10 bg-pink-600/15 border border-pink-500/30 grid place-items-center">
        <BarChart3 className="w-5 h-5 text-pink-300" />
      </div>
    </div>

    <div className="p-4 space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <FindingStat label="Latest sweep" value="40,500" sub="simulated days" />
        <FindingStat label="Favourites" value="2 / 3 / 4" sub="compared" />
        <FindingStat label="Recovery" value="L3 / L4 / L5" sub="compared" />
        <FindingStat label="Caps" value="20 / 50 / 100" sub="liability" />
      </div>

      <ResultTable
        title="Balanced profit projections"
        rows={balancedRows}
        columns={["Setup", "Avg Day", "5-Day Week", "20-Day Month", "Risk"]}
      />

      <ResultTable
        title="Higher profit potential"
        rows={potentialRows}
        columns={["Setup", "20-Day Month", "95% Drawdown", "Note"]}
        compact
      />

      <div className="grid md:grid-cols-3 gap-3 text-sm">
        <Note title="Stake scaling">
          Profit potential scales sharply with stake, but so does the bad-day drawdown.
          The &pound;1.00 setup showed the biggest monthly average, but it needs a much
          larger bank to absorb variance.
        </Note>
        <Note title="Cap effect">
          Higher caps let recovery breathe and improve target capture, especially at
          &pound;0.50 and &pound;1.00. Tight caps reduce exposure but interrupt recovery more often.
        </Note>
        <Note title="Profit projection">
          The weekly and monthly numbers are averages from repeated simulator days, not
          guarantees. The median often sits close to the full target, while loss clusters pull
          down the average.
        </Note>
      </div>
    </div>
  </div>
);

const ResultTable = ({ title, rows, columns, compact = false }) => (
  <div>
    <div className="label-xs mb-2">{title}</div>
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px]">
        <thead>
          <tr className="text-xs uppercase tracking-wider text-zinc-500 border-b border-[#2A2A2A]">
            {columns.map((col) => (
              <th key={col} className={`py-2 ${col === "Setup" ? "text-left" : "text-right"}`}>
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label || row.note} className="border-b border-[#2A2A2A]/70">
              {compact ? (
                <>
                  <td className="py-3 pr-3 text-sm text-zinc-400 font-mono">{row.config}</td>
                  <td className="py-3 pr-3 text-right text-emerald-400 font-mono">{row.month}</td>
                  <td className="py-3 pr-3 text-right text-amber-300 font-mono">{row.drawdown}</td>
                  <td className="py-3 text-right text-zinc-400 text-sm">{row.note}</td>
                </>
              ) : (
                <>
                  <td className="py-3 pr-3">
                    <div className="font-bold text-sm text-white">{row.label}</div>
                    <div className="text-xs text-zinc-500 font-mono">{row.config}</div>
                  </td>
                  <td className="py-3 pr-3 text-right text-emerald-400 font-mono">{row.day}</td>
                  <td className="py-3 pr-3 text-right text-emerald-400 font-mono">{row.week}</td>
                  <td className="py-3 pr-3 text-right text-emerald-400 font-mono">{row.month}</td>
                  <td className="py-3 text-right text-amber-300 font-mono text-xs">{row.risk}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
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

const Note = ({ title, children }) => (
  <div className="bg-[#0A0A0A] border border-[#2A2A2A] p-3">
    <div className="font-display uppercase tracking-tight text-lg mb-1">{title}</div>
    <div className="text-zinc-400 leading-relaxed">{children}</div>
  </div>
);
