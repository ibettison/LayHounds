import React from "react";

const screenshots = [
  {
    src: "/assets/website-screenshots/full-page.png",
    title: "Historical Replay workspace",
    note: "Full replay dashboard with race card, recovery chains, session history and live controls.",
    wide: true,
  },
  {
    src: "/assets/website-screenshots/session-prompt.png",
    title: "Setup prompt",
    note: "Choose replay, paper-live or live mode, then set stake, bank and daily limits.",
  },
  {
    src: "/assets/website-screenshots/daily-pnl.png",
    title: "Daily P&L journal",
    note: "Cross-session performance view showing cumulative and per-day P&L.",
  },
  {
    src: "/assets/website-screenshots/per-favourite.png",
    title: "Per-favourite recovery",
    note: "Each favourite rank keeps its own recovery status and next stake.",
  },
  {
    src: "/assets/website-screenshots/race-history.png",
    title: "Race history",
    note: "A chronological race-card record with real replay times and settled outcomes.",
  },
  {
    src: "/assets/website-screenshots/welcome.png",
    title: "Clean start screen",
    note: "A controlled environment before any session is started.",
  },
];

export const ProductScreenshotGallery = () => (
  <section className="space-y-4" data-testid="product-screenshot-gallery">
    <div className="flex items-end justify-between gap-4">
      <div>
        <div className="label-xs mb-2">Real app screens</div>
        <h2 className="font-display text-2xl sm:text-3xl uppercase tracking-tight">
          Built around the actual replay workflow
        </h2>
      </div>
      <div className="hidden sm:block text-[10px] text-zinc-500 font-mono max-w-xs text-right">
        Screenshots from Lay-Hounds Historical Replay. Interface may vary as settings change.
      </div>
    </div>

    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {screenshots.map((shot) => (
        <figure
          key={shot.src}
          className={`bg-[#141414] border border-[#2A2A2A] overflow-hidden ${
            shot.wide ? "lg:col-span-2" : ""
          }`}
        >
          <div className="bg-[#0A0A0A] border-b border-[#2A2A2A]">
            <img
              src={shot.src}
              alt={shot.title}
              loading="lazy"
              className="w-full h-auto block"
            />
          </div>
          <figcaption className="p-3">
            <div className="font-display uppercase text-sm font-bold text-white">
              {shot.title}
            </div>
            <div className="text-[11px] text-zinc-400 mt-1 leading-relaxed">
              {shot.note}
            </div>
          </figcaption>
        </figure>
      ))}
    </div>
  </section>
);
