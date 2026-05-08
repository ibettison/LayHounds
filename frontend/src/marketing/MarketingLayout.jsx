import React, { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { Menu, X, ChevronRight } from "lucide-react";
import { Button } from "../components/ui/button";

const NAV = [
  { href: "/#features", label: "Features" },
  { href: "/#how", label: "How it works" },
  { href: "/#pricing", label: "Pricing" },
  { href: "/#faq", label: "FAQ" },
];

export const MarketingHeader = () => {
  const [open, setOpen] = useState(false);
  return (
    <header
      data-testid="marketing-header"
      className="sticky top-0 z-50 bg-white/70 backdrop-blur-xl border-b border-slate-200"
    >
      <div className="max-w-7xl mx-auto px-6 md:px-12 py-4 flex items-center justify-between">
        <Link to="/" data-testid="brand-logo" className="flex items-center gap-2.5">
          <div className="w-9 h-9 bg-pink-500 grid place-items-center rounded-lg shadow-sm shadow-pink-500/30">
            <span className="text-white font-display font-black text-lg leading-none tracking-tighter">L</span>
          </div>
          <div className="font-display font-black text-xl text-slate-900 tracking-tighter leading-none">
            Lay-Hounds
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {NAV.map((n) => (
            <a
              key={n.href}
              href={n.href}
              data-testid={`nav-${n.label.toLowerCase().replace(/\s/g, "-")}`}
              className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
            >
              {n.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Link to="/app" state={{ fromMarketing: true }} data-testid="header-open-app">
            <Button className="bg-pink-500 hover:bg-pink-600 text-white rounded-lg font-semibold shadow-sm shadow-pink-500/30 transition-all hover:-translate-y-0.5">
              Open App
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </Link>
          <button
            data-testid="mobile-menu-btn"
            className="md:hidden p-2 text-slate-700"
            onClick={() => setOpen((o) => !o)}
            aria-label="menu"
          >
            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {open && (
        <nav className="md:hidden border-t border-slate-200 bg-white px-6 py-4 flex flex-col gap-3">
          {NAV.map((n) => (
            <a
              key={n.href}
              href={n.href}
              onClick={() => setOpen(false)}
              className="text-sm font-medium text-slate-700 py-1"
            >
              {n.label}
            </a>
          ))}
        </nav>
      )}
    </header>
  );
};

export const MarketingFooter = () => (
  <footer
    data-testid="marketing-footer"
    className="bg-slate-900 text-slate-400 mt-20"
  >
    <div className="max-w-7xl mx-auto px-6 md:px-12 py-16 grid grid-cols-1 md:grid-cols-4 gap-10">
      <div className="md:col-span-2 space-y-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 bg-pink-500 grid place-items-center rounded-lg">
            <span className="text-white font-display font-black text-lg leading-none">L</span>
          </div>
          <div className="font-display font-black text-xl text-white tracking-tighter">Lay-Hounds</div>
        </div>
        <p className="text-sm leading-relaxed max-w-md">
          The premier Betfair greyhound lay-betting recovery simulator.
          Built in Durham, UK.
        </p>
        <div className="text-xs font-mono uppercase tracking-widest text-slate-500">
          © 2026 Lay-Hounds · Durham, UK
        </div>
      </div>

      <div>
        <div className="text-xs font-mono uppercase tracking-widest text-slate-500 mb-4">Product</div>
        <ul className="space-y-2 text-sm">
          <li><a href="/#features" className="hover:text-white transition-colors">Features</a></li>
          <li><a href="/#how" className="hover:text-white transition-colors">How it works</a></li>
          <li><a href="/#pricing" className="hover:text-white transition-colors">Pricing</a></li>
          <li><Link to="/app" state={{ fromMarketing: true }} data-testid="footer-open-app" className="hover:text-white transition-colors">Open App</Link></li>
        </ul>
      </div>

      <div>
        <div className="text-xs font-mono uppercase tracking-widest text-slate-500 mb-4">Legal</div>
        <ul className="space-y-2 text-sm">
          <li><Link to="/terms" data-testid="footer-terms" className="hover:text-white transition-colors">Terms of Service</Link></li>
          <li><Link to="/privacy" data-testid="footer-privacy" className="hover:text-white transition-colors">Privacy Policy</Link></li>
          <li><Link to="/refund" data-testid="footer-refund" className="hover:text-white transition-colors">Refund Policy</Link></li>
          <li><a href="/#contact" className="hover:text-white transition-colors">Contact</a></li>
        </ul>
      </div>
    </div>

    <div className="border-t border-slate-800 py-5 text-center text-xs text-slate-500 px-6">
      18+. Gambling carries risk — never bet money you cannot afford to lose.{" "}
      <a href="https://www.gamcare.org.uk" target="_blank" rel="noreferrer" className="underline hover:text-white">GamCare</a>
      &nbsp;·&nbsp;
      <a href="https://www.begambleaware.org" target="_blank" rel="noreferrer" className="underline hover:text-white">BeGambleAware</a>
    </div>
  </footer>
);

export const MarketingLayout = ({ children }) => (
  <div className="min-h-screen bg-white text-slate-900 font-sans antialiased">
    <MarketingHeader />
    {children}
    <MarketingFooter />
  </div>
);
