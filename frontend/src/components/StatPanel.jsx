import React from "react";

export const StatPanel = ({ label, value, sub, tone = "default", testId, mono = true }) => {
  const toneClass = {
    default: "text-white",
    win: "text-emerald-400",
    loss: "text-red-400",
    pink: "text-pink-400",
    amber: "text-amber-400",
  }[tone];

  return (
    <div
      data-testid={testId}
      className="bg-[#141414] border border-[#2A2A2A] p-4 flex flex-col gap-2"
    >
      <div className="label-xs">{label}</div>
      <div className={`${mono ? "font-mono" : "font-display"} text-2xl font-bold ${toneClass}`}>
        {value}
      </div>
      {sub && <div className="text-xs text-zinc-500 font-mono">{sub}</div>}
    </div>
  );
};
