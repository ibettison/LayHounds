import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, XCircle, ChevronRight, Loader2, Copy, KeyRound } from "lucide-react";
import { Button } from "../components/ui/button";
import { MarketingLayout } from "../marketing/MarketingLayout";
import { API } from "../lib/api";
import { toast } from "sonner";

const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;

export const CheckoutSuccess = () => {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id") || params.get("token");
  const [state, setState] = useState({ status: "polling", licence_key: null, error: null });
  const startedAt = useRef(Date.now());

  useEffect(() => {
    if (!sessionId) {
      setState({ status: "error", licence_key: null, error: "No session_id in URL" });
      return;
    }
    let cancelled = false;
    let intervalId = null;

    const tick = async () => {
      if (cancelled) return;
      if (Date.now() - startedAt.current > POLL_TIMEOUT_MS) {
        setState({ status: "timeout", licence_key: null, error: "Payment status check timed out — refresh in a minute." });
        return;
      }
      try {
        const r = await axios.get(`${API}/payments/stripe/status/${sessionId}`);
        if (cancelled) return;
        if (r.data.payment_status === "paid") {
          clearInterval(intervalId);
          setState({ status: "paid", licence_key: r.data.licence_key, error: null });
        } else if (r.data.payment_status === "expired" || r.data.payment_status === "failed") {
          clearInterval(intervalId);
          setState({ status: r.data.payment_status, licence_key: null, error: null });
        }
      } catch (e) {
        if (cancelled) return;
        // Keep polling; transient errors are OK while Stripe finalises
      }
    };
    tick();
    intervalId = setInterval(tick, POLL_INTERVAL_MS);
    return () => { cancelled = true; clearInterval(intervalId); };
  }, [sessionId]);

  const copyKey = () => {
    if (!state.licence_key) return;
    navigator.clipboard?.writeText(state.licence_key).then(() => toast.success("Licence key copied"));
  };

  return (
    <MarketingLayout>
      <div className="max-w-2xl mx-auto px-6 md:px-12 py-24 text-center">
        {state.status === "polling" && (
          <>
            <div className="w-16 h-16 rounded-full bg-slate-100 grid place-items-center mx-auto mb-6">
              <Loader2 className="w-9 h-9 text-slate-500 animate-spin" />
            </div>
            <div className="text-xs font-mono uppercase tracking-widest text-slate-500 font-semibold mb-3">
              Finalising payment
            </div>
            <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tighter text-slate-900 mb-3">
              Hang on a moment…
            </h1>
            <p className="text-slate-600 leading-relaxed max-w-md mx-auto">
              Stripe is confirming your payment. We'll issue your licence key the moment it clears (usually a few seconds).
            </p>
          </>
        )}

        {state.status === "paid" && (
          <>
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
              Your licence key is below. Open your self-hosted LayHounds, paste it into the
              <strong className="text-slate-900"> Live Unlock Licence</strong> panel on the left sidebar, then click Activate.
            </p>

            <div
              data-testid="licence-key-display"
              className="bg-slate-900 text-pink-300 font-mono text-lg sm:text-2xl tracking-wider rounded-xl py-5 px-6 mb-3 inline-flex items-center gap-3 shadow-xl"
            >
              <KeyRound className="w-5 h-5 text-pink-400" />
              <span>{state.licence_key}</span>
              <button onClick={copyKey} className="text-pink-400 hover:text-white transition-colors" title="Copy">
                <Copy className="w-4 h-4" />
              </button>
            </div>
            <div className="text-xs text-slate-500 font-mono uppercase tracking-widest mb-8">
              Reference: {sessionId}
            </div>

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link to="/app" state={{ fromMarketing: true }} data-testid="success-open-app">
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
          </>
        )}

        {(state.status === "error" || state.status === "timeout" || state.status === "expired" || state.status === "failed") && (
          <>
            <div className="w-16 h-16 rounded-full bg-red-100 grid place-items-center mx-auto mb-6">
              <XCircle className="w-9 h-9 text-red-500" />
            </div>
            <div className="text-xs font-mono uppercase tracking-widest text-red-500 font-semibold mb-3">
              Payment {state.status}
            </div>
            <h1 className="font-display font-black text-3xl tracking-tighter text-slate-900 mb-5">
              Something went sideways.
            </h1>
            <p className="text-slate-600 leading-relaxed mb-8 max-w-lg mx-auto">
              {state.error || "Stripe didn't confirm payment. If you were charged, email hello@lay-hounds.co.uk and we'll fix it within a few hours."}
            </p>
            <Link to="/#pricing">
              <Button className="bg-pink-500 hover:bg-pink-600 text-white px-7 py-5 rounded-lg font-semibold">
                Back to pricing
              </Button>
            </Link>
          </>
        )}
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
        <Link to="/app" state={{ fromMarketing: true }}>
          <Button variant="outline" className="border-slate-300 px-7 py-5 rounded-lg font-semibold w-full sm:w-auto">
            Try Free Simulator
          </Button>
        </Link>
      </div>
    </div>
  </MarketingLayout>
);
