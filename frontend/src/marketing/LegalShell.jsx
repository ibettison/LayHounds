import React from "react";
import { Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { MarketingLayout } from "../marketing/MarketingLayout";

export const LegalShell = ({ title, lastUpdated, children }) => (
  <MarketingLayout>
    <div className="max-w-3xl mx-auto px-6 md:px-12 py-16 md:py-24">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900 mb-8" data-testid="legal-back">
        <ChevronLeft className="w-4 h-4" /> Back to home
      </Link>
      <div className="text-xs font-mono uppercase tracking-widest text-pink-600 font-semibold mb-3">Legal</div>
      <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-slate-900 mb-3">
        {title}
      </h1>
      <p className="text-sm text-slate-500 font-mono mb-12">Last updated: {lastUpdated}</p>
      <div className="legal-prose space-y-3 text-slate-600 leading-relaxed">
        {children}
      </div>
    </div>
  </MarketingLayout>
);
