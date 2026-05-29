import React, { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ChevronRight,
  Sliders,
  Layers,
  Activity,
  Zap,
  Wifi,
  LineChart,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Lock,
  Mail,
  MapPin,
  ArrowUpRight,
  Star,
  Quote,
  Smile,
} from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../components/ui/accordion";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { MarketingLayout } from "../marketing/MarketingLayout";
import { InteractiveDemo } from "../marketing/InteractiveDemo";
import { api } from "../lib/api";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] },
};

const Section = ({ id, className = "", children }) => (
  <section id={id} className={`py-20 md:py-28 ${className}`}>
    <div className="max-w-7xl mx-auto px-6 md:px-12">{children}</div>
  </section>
);

const Overline = ({ children }) => (
  <div className="text-xs font-mono uppercase tracking-[0.18em] text-pink-600 font-semibold mb-3">
    {children}
  </div>
);

const Hero = () => (
  <Section id="hero" className="pt-12 md:pt-20">
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
      <motion.div {...fadeUp} className="lg:col-span-7 space-y-7">
        <div className="inline-flex items-center gap-2 bg-pink-50 border border-pink-100 rounded-full px-3 py-1 text-xs font-mono text-pink-700 font-semibold uppercase tracking-widest">
          <span className="w-1.5 h-1.5 bg-pink-500 rounded-full animate-pulse" />
          Real Betfair · UK greyhounds
        </div>
        <h1 className="font-display font-black text-5xl sm:text-6xl md:text-7xl tracking-tighter leading-[0.95] text-slate-900">
          Lay smarter.<br />
          <span className="text-pink-500">Recover faster.</span>
        </h1>
        <p className="text-base md:text-lg text-slate-600 max-w-xl leading-relaxed">
          Test multi-level lay-recovery strategies on simulated UK greyhound races,
          stress-test your edge with Monte-Carlo, then go live on Betfair when you're ready.
          No spreadsheet hell. No real money lost in testing.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <Link to="/app" state={{ fromMarketing: true }} data-testid="hero-cta-try">
            <Button
              size="lg"
              className="bg-pink-500 hover:bg-pink-600 text-white px-8 py-6 rounded-lg font-semibold text-base shadow-lg shadow-pink-500/30 hover:shadow-xl hover:shadow-pink-500/40 hover:-translate-y-0.5 transition-all w-full sm:w-auto"
            >
              Try Free Simulator
              <ChevronRight className="w-5 h-5 ml-1" />
            </Button>
          </Link>
          <a href="#pricing" data-testid="hero-cta-pricing">
            <Button
              size="lg"
              variant="outline"
              className="border-slate-300 text-slate-700 hover:bg-slate-100 px-8 py-6 rounded-lg font-semibold text-base w-full sm:w-auto"
            >
              See pricing
            </Button>
          </a>
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 pt-4 text-xs text-slate-500 font-mono uppercase tracking-widest">
          <div className="flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5" /> No card to start</div>
          <div className="flex items-center gap-1.5"><Lock className="w-3.5 h-3.5" /> Self-hosted, your data</div>
          <div className="flex items-center gap-1.5"><Activity className="w-3.5 h-3.5" /> Live Betfair API</div>
        </div>

        {/* Social-proof avatar strip */}
        <div className="flex items-center gap-3 pt-2" data-testid="hero-social-proof">
          <div className="flex -space-x-2">
            {["Tom", "Maya", "Jack", "Priya", "Owen"].map((seed, i) => (
              <img
                key={seed}
                src={`https://api.dicebear.com/7.x/lorelei/svg?seed=${seed}&backgroundColor=fce7f3,fbcfe8,fed7aa,fef3c7,d1fae5`}
                alt=""
                width="36"
                height="36"
                loading="lazy"
                className={`w-9 h-9 rounded-full border-2 border-white bg-pink-50 ring-1 ring-slate-200`}
                style={{ zIndex: 5 - i }}
              />
            ))}
          </div>
          <div className="text-xs text-slate-600 leading-tight">
            <div className="flex items-center gap-1 text-amber-500">
              {[1, 2, 3, 4, 5].map((i) => (
                <Star key={i} className="w-3 h-3 fill-amber-400" />
              ))}
              <span className="text-slate-700 font-semibold ml-1">4.8</span>
            </div>
            <div className="text-slate-500 text-[11px] font-medium">
              Joined by 200+ UK punters this month
            </div>
          </div>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 24 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        className="lg:col-span-5"
      >
        <div className="relative">
          <div className="absolute -inset-4 bg-gradient-to-br from-pink-200 via-pink-50 to-transparent rounded-3xl blur-2xl opacity-60" />
          <div
            className="absolute -right-20 sm:-right-28 top-8 sm:top-10 z-0 w-40 sm:w-52 pointer-events-none"
            aria-hidden="true"
          >
            <img
              src="/assets/greyhound-peeking-cutout.png"
              alt=""
              loading="eager"
              className="w-full drop-shadow-2xl"
            />
          </div>
          <div className="relative z-10 rounded-2xl border border-slate-200 bg-slate-900 shadow-2xl overflow-hidden">
            <div className="flex items-center gap-1.5 px-4 py-2.5 bg-slate-800 border-b border-slate-700">
              <span className="w-2.5 h-2.5 rounded-full bg-red-400/80" />
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400/80" />
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400/80" />
              <span className="ml-3 text-[10px] font-mono text-slate-400 uppercase tracking-widest">
                lay-hounds.co.uk/app
              </span>
            </div>
            <div className="aspect-[4/3] bg-[#0A0A0A] grid place-items-center p-6">
              <div className="grid grid-cols-3 gap-3 w-full">
                {[
                  { l: "Bank", v: "£1,247.20", c: "text-emerald-400" },
                  { l: "P&L", v: "+£47.20", c: "text-emerald-400" },
                  { l: "Races", v: "23/100", c: "text-white" },
                  { l: "Stake", v: "£0.50", c: "text-white" },
                  { l: "Recovery", v: "L2", c: "text-amber-400" },
                  { l: "Win Rate", v: "84%", c: "text-emerald-400" },
                ].map((s, i) => (
                  <div key={i} className="bg-[#141414] border border-[#2A2A2A] p-3">
                    <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">
                      {s.l}
                    </div>
                    <div className={`font-mono font-bold text-sm sm:text-base mt-1 ${s.c}`}>
                      {s.v}
                    </div>
                  </div>
                ))}
                <div className="col-span-3 bg-[#141414] border border-[#2A2A2A] p-3 mt-1">
                  <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 mb-2">
                    Daily P&L
                  </div>
                  <div className="flex items-end gap-1 h-12">
                    {[20, 35, 50, 30, 45, 65, 80, 75, 90, 70].map((h, i) => (
                      <div
                        key={i}
                        className="flex-1 bg-gradient-to-t from-pink-500 to-pink-400 rounded-sm"
                        style={{ height: `${h}%` }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  </Section>
);

const FEATURES = [
  { icon: Sliders, title: "Configurable Stakes", desc: "Lay from £0.05 to £2.00 per bet, with target profit, commission and odds-range filters baked in." },
  { icon: Layers, title: "Recovery L1–L5", desc: "Pick the depth of your staircase. Recover from prior losses on the exact same favourite-rank slot." },
  { icon: Activity, title: "Monte-Carlo Preview", desc: "Run 1,500 chain simulations before you click Go. See bust rate, EV per race and worst chain loss instantly." },
  { icon: Zap, title: "Batch Racing", desc: "Step one race at a time, or burn through 50 races in a single click for fast strategy validation." },
  { icon: Wifi, title: "Real Betfair Live", desc: "Paper-Live uses real odds from real upcoming UK greyhound markets. Live mode places real lay bets." },
  { icon: LineChart, title: "Daily P&L Journal", desc: "Bank carries between sessions. Daily cumulative chart and per-session bars across every trading day." },
];

const Features = () => (
  <Section id="features" className="bg-slate-50/50 border-y border-slate-200">
    <motion.div {...fadeUp} className="text-center max-w-2xl mx-auto mb-14">
      <Overline>What's inside</Overline>
      <h2 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-slate-900">
        Built by a lay-bettor.<br />For lay-bettors.
      </h2>
      <p className="text-slate-600 mt-4 leading-relaxed">
        Every feature exists because a spreadsheet broke first. No fluff, no upsell tier-traps —
        the simulator is fully free, forever.
      </p>
    </motion.div>

    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {FEATURES.map((f, i) => (
        <motion.div
          key={f.title}
          {...fadeUp}
          transition={{ ...fadeUp.transition, delay: i * 0.05 }}
          data-testid={`feature-${f.title.toLowerCase().replace(/[^a-z]/g, "-")}`}
          className="group bg-white rounded-xl p-7 border border-slate-200 hover:-translate-y-1 hover:shadow-lg hover:border-pink-300 transition-all"
        >
          <div className="w-10 h-10 rounded-lg bg-pink-50 grid place-items-center mb-5 group-hover:bg-pink-500 group-hover:rotate-3 transition-all">
            <f.icon className="w-5 h-5 text-pink-500 group-hover:text-white transition-colors" />
          </div>
          <h3 className="font-display font-bold text-xl tracking-tight text-slate-900 mb-2">
            {f.title}
          </h3>
          <p className="text-sm text-slate-600 leading-relaxed">{f.desc}</p>
        </motion.div>
      ))}
    </div>
  </Section>
);

const STEPS = [
  {
    n: "01",
    t: "Configure your strategy",
    d: "Pick your stake, recovery depth (L1–L5), liability cap, commission and odds range. Monte-Carlo previews show your projected bust rate before you risk a penny.",
    img: "https://images.unsplash.com/photo-1486312338219-ce68d2c6f44d?w=720&h=480&auto=format&fit=crop&q=80",
    alt: "Setting up the strategy on a laptop",
  },
  {
    n: "02",
    t: "Test in the simulator",
    d: "Run individual races or batch 50 at a time on simulated UK greyhound fields. Bank carries between sessions so you can stress-test over hundreds of days.",
    img: "https://images.unsplash.com/photo-1551836022-deb4988cc6c0?w=720&h=480&auto=format&fit=crop&q=80",
    alt: "Watching the dashboard run through races",
  },
  {
    n: "03",
    t: "Unlock and go live",
    d: "Subscribe to Live Mode (£19.99/mo). Same UI, but Paper-Live uses real Betfair odds and Live mode places real lay bets on your Betfair account.",
    img: "https://images.unsplash.com/photo-1463453091185-61582044d556?w=720&h=480&auto=format&fit=crop&q=80",
    alt: "Relaxed and confident after going live",
  },
];

const LifestyleBanner = () => (
  <section className="relative" data-testid="lifestyle-banner">
    <div className="max-w-7xl mx-auto px-6 md:px-12 py-12 md:py-16">
      <div className="relative rounded-3xl overflow-hidden shadow-2xl">
        <img
          src="https://images.unsplash.com/photo-1521119989659-a83eee488004?w=1600&h=700&auto=format&fit=crop&q=80"
          alt="Friends celebrating together"
          className="w-full h-[280px] sm:h-[360px] md:h-[420px] object-cover"
          loading="lazy"
        />
        <div className="absolute inset-0 bg-gradient-to-tr from-slate-900/80 via-slate-900/40 to-transparent" />
        <div className="absolute inset-0 flex items-center px-8 sm:px-14">
          <motion.div {...fadeUp} className="max-w-xl text-white">
            <div className="text-xs font-mono uppercase tracking-[0.18em] text-pink-300 font-semibold mb-3">
              Made for the punters
            </div>
            <h3 className="font-display font-black text-3xl sm:text-4xl md:text-5xl tracking-tighter leading-[1.05]">
              Saturday afternoons,<br />finally relaxing.
            </h3>
            <p className="text-sm sm:text-base text-slate-200 leading-relaxed mt-4 max-w-md">
              Punters who switched to Lay-Hounds tell us the same thing: the spreadsheet
              stress is gone. Watch the Monte-Carlo do the worrying so you can enjoy the racing.
            </p>
          </motion.div>
        </div>
      </div>
    </div>
  </section>
);

const HowItWorks = () => (
  <Section id="how">
    <motion.div {...fadeUp} className="max-w-2xl mb-14">
      <Overline>How it works</Overline>
      <h2 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-slate-900">
        Three steps from idea to live bet.
      </h2>
    </motion.div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {STEPS.map((s, i) => (
        <motion.div
          key={s.n}
          {...fadeUp}
          transition={{ ...fadeUp.transition, delay: i * 0.1 }}
          data-testid={`how-step-${s.n}`}
          className="group relative bg-white border border-slate-200 rounded-xl overflow-hidden hover:shadow-lg hover:-translate-y-0.5 transition-all"
        >
          <div className="relative h-44 sm:h-48 overflow-hidden">
            <img
              src={s.img}
              alt={s.alt}
              loading="lazy"
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-white/30 via-transparent to-transparent" />
            <div className="absolute top-3 left-3 bg-white/95 backdrop-blur px-2.5 py-1 rounded-md font-mono font-bold text-pink-600 text-[10px] tracking-widest shadow-sm">
              STEP / {s.n}
            </div>
          </div>
          <div className="p-7">
            <h3 className="font-display font-bold text-2xl tracking-tight text-slate-900 mb-3">
              {s.t}
            </h3>
            <p className="text-sm text-slate-600 leading-relaxed">{s.d}</p>
          </div>
        </motion.div>
      ))}
    </div>
  </Section>
);

const Demo = () => (
  <Section id="demo" className="bg-slate-50/50 border-y border-slate-200">
    <motion.div {...fadeUp} className="text-center max-w-2xl mx-auto mb-12">
      <Overline>Live tour</Overline>
      <h2 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-slate-900">
        See it move.
      </h2>
      <p className="text-slate-600 mt-4 leading-relaxed">
        10 races. Real recovery math. Watch a chain bust into L2 and crawl back to profit —
        before you've even picked your stake.
      </p>
    </motion.div>

    <motion.div {...fadeUp}>
      <InteractiveDemo />
    </motion.div>
  </Section>
);

const SimulationSweep = () => (
  <Section id="simulation-sweep" className="bg-white">
    <motion.div {...fadeUp} className="text-center max-w-3xl mx-auto mb-12">
      <Overline>Latest simulator sweep</Overline>
      <h2 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-slate-900">
        Stake levels compared.
      </h2>
      <p className="text-slate-600 mt-4 leading-relaxed">
        We ran 40,500 simulated 20-race days across &pound;0.05, &pound;0.50 and
        &pound;1.00 stakes, with recovery levels 3-5. Commission stayed fixed at 5%.
      </p>
    </motion.div>

    <motion.div {...fadeUp} className="grid md:grid-cols-3 gap-4">
      {[
        {
          title: "Small stake",
          config: <>L5 / 4 favs / stake &pound;0.05 / cap &pound;100</>,
          avg: <>&pound;7.66 weekly / &pound;30.65 monthly avg</>,
          risk: "95% positive days / 4% bust",
        },
        {
          title: "Mid stake",
          config: <>L5 / 3 favs / stake &pound;0.50 / cap &pound;100</>,
          avg: <>&pound;44.79 weekly / &pound;179.15 monthly avg</>,
          risk: "77% positive days / 23% bust",
        },
        {
          title: "Aggressive",
          config: <>L3 / 4 favs / stake &pound;1.00 / cap &pound;100</>,
          avg: <>&pound;99.71 weekly / &pound;398.83 monthly avg</>,
          risk: <>&pound;116.18 95% drawdown / 65% bust</>,
        },
      ].map(({ title, config, avg, risk }) => (
        <div key={title} className="rounded-xl border border-slate-200 bg-slate-50 p-5 shadow-sm">
          <div className="text-xs font-mono uppercase tracking-widest text-pink-600 font-bold mb-3">{title}</div>
          <div className="text-sm text-slate-600 leading-relaxed mb-4">{config}</div>
          <div className="font-mono text-lg font-bold text-emerald-600">{avg}</div>
          <div className="font-mono text-xs text-slate-500 mt-1">{risk}</div>
        </div>
      ))}
    </motion.div>
  </Section>
);

const TESTIMONIALS = [
  {
    photo: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=200&h=200&auto=format&fit=crop&q=80",
    name: "Liam",
    location: "Newcastle",
    quote:
      "I'd been running my recovery staircase in a battered spreadsheet for two years. Lay-Hounds replaced 800 lines of formulas in an afternoon — and the Monte-Carlo preview saved me from a strategy that would have busted me twice a week.",
    tag: "Free Simulator user",
  },
  {
    photo: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=200&h=200&auto=format&fit=crop&q=80",
    name: "Aisha",
    location: "London",
    quote:
      "Honestly thought it was too good to be true. Tried the simulator, ran 50 races in a click, then upgraded to Live the same evening. The bank-carryover daily chart is the bit I love most — finally a real journal.",
    tag: "Live subscriber",
  },
  {
    photo: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&h=200&auto=format&fit=crop&q=80",
    name: "Mark",
    location: "Bristol",
    quote:
      "The cap-protection in Cap Crisis mode is what sold me — I've watched chains bust safely with my own eyes before risking a real penny. Worth £19.99 just for the peace of mind on Saturday afternoons.",
    tag: "Live subscriber",
  },
];

const Testimonials = () => (
  <Section id="testimonials">
    <motion.div {...fadeUp} className="text-center max-w-2xl mx-auto mb-14">
      <Overline>Loved by lay-bettors</Overline>
      <h2 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-slate-900">
        People are pretty pleased.
      </h2>
      <p className="text-slate-600 mt-4 leading-relaxed">
        Real quotes from real users. (We change the names — punters are private people.)
      </p>
    </motion.div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {TESTIMONIALS.map((t, i) => (
        <motion.div
          key={t.name}
          {...fadeUp}
          transition={{ ...fadeUp.transition, delay: i * 0.08 }}
          data-testid={`testimonial-${t.name.toLowerCase()}`}
          className="bg-white border border-slate-200 rounded-2xl p-7 hover:-translate-y-1 hover:shadow-lg hover:border-pink-200 transition-all flex flex-col"
        >
          <Quote className="w-6 h-6 text-pink-300 mb-4" />
          <p className="text-slate-700 leading-relaxed text-sm flex-1">
            &ldquo;{t.quote}&rdquo;
          </p>
          <div className="flex items-center gap-1 text-amber-500 mt-5">
            {[1, 2, 3, 4, 5].map((s) => (
              <Star key={s} className="w-3.5 h-3.5 fill-amber-400" />
            ))}
          </div>
          <div className="flex items-center gap-3 mt-4 pt-4 border-t border-slate-100">
            <img
              src={t.photo}
              alt={`${t.name} from ${t.location}`}
              width="44"
              height="44"
              loading="lazy"
              className="w-11 h-11 rounded-full object-cover bg-slate-100"
            />
            <div>
              <div className="font-display font-bold text-slate-900 text-base leading-tight">
                {t.name}
              </div>
              <div className="text-xs text-slate-500 font-mono uppercase tracking-widest mt-0.5">
                {t.location} · {t.tag}
              </div>
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  </Section>
);

const Pricing = () => {
  const [loading, setLoading] = useState(null);

  const startCheckout = async (provider) => {
    setLoading(provider);
    try {
      const res = await api.startCheckout(provider);
      if (res.url) {
        window.location.href = res.url;
      } else {
        toast.message(res.message || "Checkout coming soon — try again later or use the other payment option.");
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not start checkout");
    } finally {
      setLoading(null);
    }
  };

  return (
    <Section id="pricing">
      <motion.div {...fadeUp} className="text-center max-w-2xl mx-auto mb-14">
        <Overline>Simple pricing</Overline>
        <h2 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-slate-900">
          Free to test. Pay to go live.
        </h2>
        <p className="text-slate-600 mt-4 leading-relaxed">
          The simulator is permanently free. Pay only when you're ready to wire it to real Betfair markets.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
        {/* Free */}
        <motion.div
          {...fadeUp}
          data-testid="pricing-tier-free"
          className="bg-white border border-slate-200 rounded-2xl p-8 hover:shadow-md transition-all"
        >
          <div className="text-xs font-mono uppercase tracking-widest text-slate-500 mb-2">
            Simulator
          </div>
          <div className="font-display font-black text-5xl tracking-tighter text-slate-900">
            Free
          </div>
          <div className="text-sm text-slate-500 mt-1 mb-6">forever, no card</div>

          <ul className="space-y-3 mb-8">
            {[
              "Unlimited fake UK greyhound races",
              "Recovery levels L1 – L5",
              "Monte-Carlo cap preview",
              "Batch racing (1 / 5 / 10 / 25 / 50)",
              "Daily P&L journal + bank carryover",
              "Self-hosted on your own VPS",
            ].map((f) => (
              <li key={f} className="flex items-start gap-2.5 text-sm text-slate-700">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                {f}
              </li>
            ))}
            <li className="flex items-start gap-2.5 text-sm text-slate-400 line-through">
              <XCircle className="w-4 h-4 text-slate-300 mt-0.5 shrink-0" />
              Real Betfair odds (Paper-Live)
            </li>
            <li className="flex items-start gap-2.5 text-sm text-slate-400 line-through">
              <XCircle className="w-4 h-4 text-slate-300 mt-0.5 shrink-0" />
              Real lay bets (Live mode)
            </li>
          </ul>
          <Link to="/app" state={{ fromMarketing: true }} data-testid="pricing-free-cta">
            <Button
              variant="outline"
              className="w-full border-slate-300 text-slate-700 hover:bg-slate-100 rounded-lg font-semibold py-6"
            >
              Open Simulator
            </Button>
          </Link>
        </motion.div>

        {/* Live Unlock */}
        <motion.div
          {...fadeUp}
          transition={{ ...fadeUp.transition, delay: 0.1 }}
          data-testid="pricing-tier-live"
          className="relative bg-slate-900 text-white border-2 border-pink-500 rounded-2xl p-8 shadow-xl shadow-pink-500/20"
        >
          <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-pink-500 text-white text-xs font-mono font-bold uppercase tracking-widest px-3 py-1 rounded-full">
            Most Popular
          </div>
          <div className="text-xs font-mono uppercase tracking-widest text-pink-300 mb-2">
            Live Unlock
          </div>
          <div className="font-display font-black text-5xl tracking-tighter">
            £19.99<span className="text-2xl text-slate-400 font-normal">/mo</span>
          </div>
          <div className="text-sm text-slate-400 mt-1 mb-6">cancel anytime</div>

          <ul className="space-y-3 mb-8">
            {[
              "Everything in Free",
              "Paper-Live mode (real Betfair odds)",
              "Live mode (real lay bets)",
              "Liability-cap bust protection",
              "Priority email support",
              "Free updates while subscribed",
            ].map((f) => (
              <li key={f} className="flex items-start gap-2.5 text-sm text-slate-200">
                <CheckCircle2 className="w-4 h-4 text-pink-400 mt-0.5 shrink-0" />
                {f}
              </li>
            ))}
          </ul>

          <div className="space-y-2.5">
            <Button
              data-testid="pricing-stripe-btn"
              onClick={() => startCheckout("stripe")}
              disabled={loading === "stripe"}
              className="w-full bg-pink-500 hover:bg-pink-600 text-white rounded-lg font-semibold py-6 shadow-lg shadow-pink-500/30 hover:-translate-y-0.5 transition-all disabled:opacity-60"
            >
              {loading === "stripe" ? "Redirecting…" : "Pay with Card"}
            </Button>
            <Button
              data-testid="pricing-paypal-btn"
              onClick={() => startCheckout("paypal")}
              disabled={loading === "paypal"}
              variant="outline"
              className="w-full bg-white text-slate-900 hover:bg-slate-100 border-white rounded-lg font-semibold py-6 transition-all disabled:opacity-60"
            >
              {loading === "paypal" ? "Redirecting…" : "Pay with PayPal"}
            </Button>
          </div>

          <div className="flex items-center justify-center gap-3 mt-5 text-xs font-mono uppercase tracking-widest text-slate-500">
            <Lock className="w-3 h-3" />
            <span>Secured by Stripe & PayPal</span>
          </div>
        </motion.div>
      </div>
    </Section>
  );
};

const FAQS = [
  {
    q: "Is lay-betting on Betfair legal in the UK?",
    a: "Yes. Betfair is a UK Gambling Commission–licensed exchange and lay-betting is a standard market type. You must be 18+ and use your own funded Betfair account. Lay-Hounds is a strategy tool — it doesn't accept your money for bets, it places them on your behalf via the official Betfair API.",
  },
  {
    q: "Do I need a Betfair account?",
    a: "Only if you want to use Paper-Live or Live mode. The free Simulator works entirely on synthetic UK greyhound races and needs no external accounts. To go live you'll need a Betfair account, an App Key (free for delayed data, paid for live data) and your username/password — all entered into your own self-hosted .env file.",
  },
  {
    q: "What does the £19.99/month Live Unlock actually buy me?",
    a: "A licence key that unlocks Paper-Live and Live modes inside the simulator. The Free Simulator is unaffected and works permanently without payment. You self-host on your own UK/EU VPS (~£6/mo from Hetzner, OVH, Fasthosts etc.).",
  },
  {
    q: "Can I cancel?",
    a: "Yes, anytime — billing pauses at the end of your current period. You keep Live access until the period ends, then revert to Free Simulator. No 'win-back' calls or pop-ups.",
  },
  {
    q: "Do you take a cut of my winnings?",
    a: "No. Lay-Hounds is a flat subscription. Whatever you win or lose on Betfair is yours. Lay-Hounds never sees your bet results, only the metadata your simulator records locally.",
  },
  {
    q: "Why self-hosted instead of cloud-hosted?",
    a: "Two reasons. First: Betfair geo-blocks non-UK/EU IPs, so the backend has to run somewhere on UK/EU soil. Second: your Betfair credentials never leave your server. We provide a one-command deploy.sh that installs everything on a fresh Ubuntu 22.04/24.04 box in ~3 minutes.",
  },
  {
    q: "Do I get my money back if it doesn't work?",
    a: "Yes — 14-day money-back guarantee, no questions asked. Email us at the address below within 14 days of your first payment and we'll refund in full. After that, you can cancel future renewals anytime.",
  },
  {
    q: "Is recovery-staircase betting profitable?",
    a: "It's a tool, not a guarantee. Lay-Hounds shows you exactly how a strategy would have performed across thousands of simulated chains, including bust rates and worst-case drawdowns. Use the Monte-Carlo preview to find configurations with positive expected value before going live. Past performance does not guarantee future results.",
  },
];

const FAQ = () => (
  <Section id="faq">
    <motion.div {...fadeUp} className="max-w-3xl mx-auto">
      <div className="text-center mb-12">
        <Overline>Questions</Overline>
        <h2 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-slate-900">
          The honest FAQ.
        </h2>
      </div>

      <Accordion type="single" collapsible className="space-y-1" data-testid="faq-accordion">
        {FAQS.map((f, i) => (
          <AccordionItem
            key={i}
            value={`q-${i}`}
            className="border-b border-slate-200 px-2"
            data-testid={`faq-item-${i}`}
          >
            <AccordionTrigger className="font-display font-bold text-lg text-left text-slate-900 hover:no-underline py-5">
              {f.q}
            </AccordionTrigger>
            <AccordionContent className="text-slate-600 leading-relaxed text-base pb-6">
              {f.a}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </motion.div>
  </Section>
);

const SimulatorInfo = () => (
  <Section id="simulator-info">
    <motion.div {...fadeUp} className="max-w-5xl mx-auto">
      <div className="bg-zinc-950 border border-zinc-800 p-8 md:p-12">
        <Overline className="text-emerald-400">Realistic Demo Simulation</Overline>
        <h2 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-white leading-tight mt-3">
          Built Using Real Racing Statistics
        </h2>
        <p className="text-zinc-300 mt-5 leading-relaxed text-lg">
          Our simulator has been carefully engineered using legitimate industry
          favourite-performance statistics and realistic UK race modelling data
          to create an experience that feels as close to live racing as possible.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-10">
          {[
            ["Race Intelligence", "Weighted using race grades, distance bands, track categories, and historical favourite-performance data."],
            ["Realistic Market Behaviour", "Market-style odds distribution to recreate believable race outcomes and betting behaviour."],
            ["Balanced Randomisation", "Favourites perform better long-term, but each race includes natural variance — keeps it realistic."],
            ["Real-World Limitations", "Live-racing micro-events like blocking, barging and split-second incidents cannot be perfectly replicated."],
          ].map(([title, body]) => (
            <div key={title} className="bg-zinc-900/60 border border-zinc-800 p-5">
              <h3 className="font-semibold text-lg text-white mb-2">{title}</h3>
              <p className="text-zinc-400 text-sm leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
        <div className="bg-emerald-500/10 border border-emerald-500/30 p-6 mt-8">
          <p className="text-zinc-200 leading-relaxed">
            Over thousands of internal test simulations, the system has
            consistently produced results closely aligned with genuine UK
            industry averages — helping ensure races feel fair, believable,
            and authentic.
          </p>
        </div>
      </div>
    </motion.div>
  </Section>
);

const VPSReferral = () => (
  <Section id="hosting">
    <motion.div {...fadeUp} className="max-w-6xl mx-auto">
      <div className="relative overflow-hidden border border-zinc-800 bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 p-8 md:p-12">
        <div className="absolute top-0 right-0 opacity-5 text-[180px] font-black leading-none select-none text-white">VPS</div>
        <div className="relative z-10 grid md:grid-cols-2 gap-10 items-center">
          <div>
            <Overline className="text-pink-400">Recommended Hosting</Overline>
            <h2 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-white leading-tight mt-3">
              Run LayHounds on a Fast UK VPS
            </h2>
            <p className="text-zinc-300 mt-5 leading-relaxed text-lg">
              For the best Betfair connectivity and reliable 24/7 uptime, we
              recommend a UK-based VPS provider.
            </p>
            <div className="mt-8 space-y-3">
              {["UK-based infrastructure",
                "Ideal for Betfair API access",
                "Perfect for live-betting uptime",
                "Works great with Ubuntu + Nginx"].map((item) => (
                <div key={item} className="flex items-center gap-3 text-zinc-200">
                  <div className="w-2 h-2 rounded-full bg-pink-400" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
            <a
              href="https://www.fasthosts.co.uk/referral?referral=37u6fp7gtbgc9n"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-3 mt-8 bg-pink-600 hover:bg-pink-500 text-white px-7 py-4 font-bold transition-all hover:scale-[1.02] shadow-lg"
              data-testid="fasthosts-referral-cta"
            >
              Launch Your VPS →
            </a>
          </div>
          <div className="bg-black/70 border border-zinc-800 p-8 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-white font-display font-bold text-2xl">Recommended Setup</h3>
              <span className="bg-emerald-500/20 text-emerald-400 px-3 py-1 text-xs font-bold uppercase tracking-wider border border-emerald-500/30">Optimised</span>
            </div>
            <div className="space-y-4">
              {[["OS", "Ubuntu 22.04 / 24.04"], ["RAM", "2 GB+"], ["CPU", "1 vCPU+"],
                ["Region", "UK / EU"], ["Best For", "Betfair Trading"]].map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-zinc-800 pb-3">
                  <span className="text-zinc-400">{k}</span>
                  <span className="text-white font-semibold">{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  </Section>
);

const Contact = () => {
  const [form, setForm] = useState({ email: "", message: "" });
  const [sending, setSending] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.email || !form.message) {
      toast.error("Please fill in both fields");
      return;
    }
    setSending(true);
    try {
      await api.contact(form);
      toast.success("Message sent — we'll get back within 1 business day");
      setForm({ email: "", message: "" });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not send message");
    } finally {
      setSending(false);
    }
  };

  return (
    <Section id="contact" className="bg-slate-50/50 border-t border-slate-200">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-start max-w-5xl mx-auto">
        <motion.div {...fadeUp}>
          <Overline>Get in touch</Overline>
          <h2 className="font-display font-black text-4xl sm:text-5xl tracking-tighter text-slate-900 mb-5">
            Real human, real reply.
          </h2>
          <p className="text-slate-600 leading-relaxed mb-8">
            Lay-Hounds is built and supported by a small team in Durham. Drop us a line —
            partnerships, feature requests, refunds, anything.
          </p>

          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-3 text-slate-700">
              <div className="w-9 h-9 rounded-lg bg-pink-50 grid place-items-center">
                <Mail className="w-4 h-4 text-pink-500" />
              </div>
              <a href="mailto:hello@lay-hounds.co.uk" className="hover:text-slate-900">
                hello@lay-hounds.co.uk
              </a>
            </div>
            <div className="flex items-center gap-3 text-slate-700">
              <div className="w-9 h-9 rounded-lg bg-pink-50 grid place-items-center">
                <MapPin className="w-4 h-4 text-pink-500" />
              </div>
              <span>Durham, United Kingdom</span>
            </div>
          </div>

          {/* Founder card */}
          <div className="mt-8 bg-white border border-slate-200 rounded-2xl p-5 flex items-center gap-4 shadow-sm" data-testid="founder-card">
            <img
              src="https://images.unsplash.com/photo-1517841905240-472988babdf9?w=200&h=200&auto=format&fit=crop&q=80"
              alt="Tom, Lay-Hounds founder"
              width="64"
              height="64"
              loading="lazy"
              className="w-16 h-16 rounded-full object-cover bg-slate-100 shrink-0"
            />
            <div>
              <div className="flex items-center gap-1.5 text-xs font-mono uppercase tracking-widest text-pink-600 font-semibold">
                <Smile className="w-3.5 h-3.5" /> Friendly humans behind it
              </div>
              <div className="font-display font-bold text-slate-900 mt-1">Tom &amp; the Durham crew</div>
              <p className="text-xs text-slate-600 leading-relaxed mt-1">
                Built by a small team of recreational lay-bettors who got sick of broken spreadsheets.
                Replies usually within a day — often within an hour on weekends.
              </p>
            </div>
          </div>
        </motion.div>

        <motion.form
          {...fadeUp}
          transition={{ ...fadeUp.transition, delay: 0.1 }}
          onSubmit={submit}
          data-testid="contact-form"
          className="bg-white border border-slate-200 rounded-2xl p-7 shadow-sm space-y-4"
        >
          <div className="space-y-2">
            <Label htmlFor="contact-email" className="text-xs font-mono uppercase tracking-widest text-slate-500">
              Your email
            </Label>
            <Input
              id="contact-email"
              type="email"
              required
              data-testid="contact-email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="you@example.com"
              className="rounded-lg border-slate-300 focus:border-pink-400 focus:ring-pink-400"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="contact-msg" className="text-xs font-mono uppercase tracking-widest text-slate-500">
              Message
            </Label>
            <Textarea
              id="contact-msg"
              required
              rows={5}
              data-testid="contact-message"
              value={form.message}
              onChange={(e) => setForm({ ...form, message: e.target.value })}
              placeholder="Tell us what you need…"
              className="rounded-lg border-slate-300 focus:border-pink-400 focus:ring-pink-400"
            />
          </div>
          <Button
            type="submit"
            disabled={sending}
            data-testid="contact-submit"
            className="w-full bg-pink-500 hover:bg-pink-600 text-white rounded-lg font-semibold py-6 shadow-md shadow-pink-500/20 hover:-translate-y-0.5 transition-all disabled:opacity-60"
          >
            {sending ? "Sending…" : "Send message"}
          </Button>
        </motion.form>
      </div>
    </Section>
  );
};

export default function Landing() {
  return (
    <MarketingLayout>
      <Hero />
      <Features />
      <LifestyleBanner />
      <HowItWorks />
      <Demo />
      <SimulationSweep />
      <Testimonials />
      <Pricing />
      <FAQ />
      <SimulatorInfo />
      <VPSReferral />
      <Contact />
    </MarketingLayout>
  );
}
