import React from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, XCircle, ChevronRight } from "lucide-react";
import { Button } from "../components/ui/button";
import { MarketingLayout } from "../marketing/MarketingLayout";

export const CheckoutSuccess = () => {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id") || params.get("token");

  return (
    <MarketingLayout>
      <div className="max-w-2xl mx-auto px-6 md:px-12 py-24 text-center">
        <div className="w-16 h-16 rounded-full bg-emerald-100 grid place-items-center mx-auto mb-6">
          <CheckCircle2 className="w-9 h-9 text-emerald-600" />
        </div>
        <div className="text-xs font-mono uppercase tracking-widest text-emerald-600 font-semibold mb-3">
          Payment received
        </div>
        <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-slate-900 mb-5">
          Welcome to Lay-Hounds Live.
        </h1>
        <p className="text-slate-600 leading-relaxed mb-8 max-w-lg mx-auto">
          Your licence key has been emailed to you. Paste it into your self-hosted simulator
          (Settings → Activate Licence) to unlock Paper-Live and Live modes.
        </p>
        {sessionId && (
          <div className="inline-block bg-slate-50 border border-slate-200 rounded-lg px-4 py-2 text-xs font-mono text-slate-500 mb-8" data-testid="checkout-session-id">
            Reference: {sessionId}
          </div>
        )}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link to="/app" data-testid="success-open-app">
            <Button className="bg-pink-500 hover:bg-pink-600 text-white px-7 py-5 rounded-lg font-semibold shadow-md shadow-pink-500/30 hover:-translate-y-0.5 transition-all w-full sm:w-auto">
              Open the App
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </Link>
          <Link to="/">
            <Button variant="outline" className="border-slate-300 px-7 py-5 rounded-lg font-semibold w-full sm:w-auto">
              Back to home
            </Button>
          </Link>
        </div>
      </div>
    </MarketingLayout>
  );
};

export const CheckoutCancel = () => (
  <MarketingLayout>
    <div className="max-w-2xl mx-auto px-6 md:px-12 py-24 text-center">
      <div className="w-16 h-16 rounded-full bg-slate-100 grid place-items-center mx-auto mb-6">
        <XCircle className="w-9 h-9 text-slate-500" />
      </div>
      <div className="text-xs font-mono uppercase tracking-widest text-slate-500 font-semibold mb-3">
        Payment cancelled
      </div>
      <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-slate-900 mb-5">
        No charge made.
      </h1>
      <p className="text-slate-600 leading-relaxed mb-8 max-w-lg mx-auto">
        You closed the checkout window before completing payment. The free Simulator is
        still fully available — try it before you buy.
      </p>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Link to="/#pricing" data-testid="cancel-back-pricing">
          <Button className="bg-pink-500 hover:bg-pink-600 text-white px-7 py-5 rounded-lg font-semibold shadow-md shadow-pink-500/30 w-full sm:w-auto">
            Back to pricing
          </Button>
        </Link>
        <Link to="/app">
          <Button variant="outline" className="border-slate-300 px-7 py-5 rounded-lg font-semibold w-full sm:w-auto">
            Try Free Simulator
          </Button>
        </Link>
      </div>
    </div>
  </MarketingLayout>
);
