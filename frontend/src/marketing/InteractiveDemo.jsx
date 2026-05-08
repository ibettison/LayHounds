import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Play, Pause, RotateCcw, Trophy, ShieldAlert, ShieldCheck, ArrowUpRight, Shuffle } from "lucide-react";
import { Button } from "../components/ui/button";

// ---------- Demo configuration ----------
const COMMISSION = 0.05;
const RACE_DURATION_MS = 1100;       // "running" animation
const RESOLVE_PAUSE_MS = 1600;       // pause after a result before next race
const TOTAL_RACES = 10;

// 10 hand-scripted races chosen to showcase recovery in action.
//   F1 = lowest-odds dog, F2 = second lowest. Winner trap is the dog that crosses the line first.
//   When F1 / F2 wins, our LAY bet on it loses (we pay liability).
//   When any other trap wins, our LAY bet wins (we collect stake minus commission).
const RACES_RECOVERY = [
  { v: "Sheffield", d: [
    { trap: 1, name: "Swift Iconic",     odds: 2.4 },
    { trap: 2, name: "Droopys Sydney",   odds: 3.2 },
    { trap: 3, name: "Ballymac Vic",     odds: 4.8 },
    { trap: 4, name: "Hovex Bolt",       odds: 6.5 },
    { trap: 5, name: "Rough Sailor",     odds: 9.0 },
    { trap: 6, name: "King Turbo",       odds: 12.0 },
  ], w: 4 },                                // mid-pack winner → both lays WIN
  { v: "Crayford", d: [
    { trap: 1, name: "Pestana Rocky",    odds: 2.6 },
    { trap: 2, name: "Newinn Taylor",    odds: 3.4 },
    { trap: 3, name: "Coolavanny Aunt",  odds: 5.0 },
    { trap: 4, name: "Skywalker Logan",  odds: 7.2 },
    { trap: 5, name: "Magical Bale",     odds: 10.0 },
    { trap: 6, name: "Imperial Spirit",  odds: 14.0 },
  ], w: 1 },                                // F1 wins → lay loss, F1 → L1
  { v: "Romford", d: [
    { trap: 1, name: "Burgess Bullet",   odds: 2.8 },
    { trap: 2, name: "Templeogue Whip",  odds: 3.5 },
    { trap: 3, name: "Crash Bandicoot",  odds: 4.6 },
    { trap: 4, name: "Loughteen Blanco", odds: 7.5 },
    { trap: 5, name: "Yahoo Hippy",      odds: 9.8 },
    { trap: 6, name: "Slippy Bullet",    odds: 13.5 },
  ], w: 3 },                                // mid wins → F1 L1 recovery WINS (big swing!), F2 clean
  { v: "Nottingham", d: [
    { trap: 1, name: "Tullymurry Act",   odds: 2.5 },
    { trap: 2, name: "Westmead Hawk",    odds: 3.0 },
    { trap: 3, name: "Bockos Doomie",    odds: 5.5 },
    { trap: 4, name: "Fearless Storm",   odds: 7.8 },
    { trap: 5, name: "Toolatetosell",    odds: 10.0 },
    { trap: 6, name: "Dazzling Sunset",  odds: 13.0 },
  ], w: 2 },                                // F2 wins → F2 → L1
  { v: "Sunderland", d: [
    { trap: 1, name: "Ballyboden Boss",  odds: 2.7 },
    { trap: 2, name: "Crossfield Storm", odds: 3.6 },
    { trap: 3, name: "Swift Falcon",     odds: 4.9 },
    { trap: 4, name: "Jaytee Yankee",    odds: 7.0 },
    { trap: 5, name: "Romeo Magico",     odds: 9.5 },
    { trap: 6, name: "Droopys Verve",    odds: 12.5 },
  ], w: 2 },                                // F2 wins again → F2 → L2 (drama)
  { v: "Crayford", d: [
    { trap: 1, name: "Kilgraney Rumble", odds: 2.9 },
    { trap: 2, name: "Ballyanne Sim",    odds: 3.8 },
    { trap: 3, name: "Skywalker Logan",  odds: 5.0 },
    { trap: 4, name: "Hovex Bolt",       odds: 7.5 },
    { trap: 5, name: "Coolavanny Aunt",  odds: 10.0 },
    { trap: 6, name: "Magical Bale",     odds: 14.0 },
  ], w: 4 },                                // mid wins → F2 L2 recovery WINS (huge), F1 clean
  { v: "Sheffield", d: [
    { trap: 1, name: "Newinn Taylor",    odds: 2.6 },
    { trap: 2, name: "Pestana Rocky",    odds: 3.3 },
    { trap: 3, name: "Burgess Bullet",   odds: 4.7 },
    { trap: 4, name: "Imperial Spirit",  odds: 7.0 },
    { trap: 5, name: "King Turbo",       odds: 9.5 },
    { trap: 6, name: "Tullymurry Act",   odds: 13.0 },
  ], w: 5 },                                // mid wins → both clean wins
  { v: "Romford", d: [
    { trap: 1, name: "Crash Bandicoot",  odds: 2.5 },
    { trap: 2, name: "Bockos Doomie",    odds: 3.4 },
    { trap: 3, name: "Westmead Hawk",    odds: 4.8 },
    { trap: 4, name: "Templeogue Whip",  odds: 7.2 },
    { trap: 5, name: "Loughteen Blanco", odds: 9.8 },
    { trap: 6, name: "Yahoo Hippy",      odds: 13.0 },
  ], w: 1 },                                // F1 wins → F1 → L1
  { v: "Nottingham", d: [
    { trap: 1, name: "Fearless Storm",   odds: 2.7 },
    { trap: 2, name: "Ballyboden Boss",  odds: 3.6 },
    { trap: 3, name: "Crossfield Storm", odds: 5.0 },
    { trap: 4, name: "Swift Falcon",     odds: 7.0 },
    { trap: 5, name: "Jaytee Yankee",    odds: 9.5 },
    { trap: 6, name: "Romeo Magico",     odds: 13.5 },
  ], w: 1 },                                // F1 wins again → F1 → L2 (climax)
  { v: "Crayford", d: [
    { trap: 1, name: "Slippy Bullet",    odds: 2.8 },
    { trap: 2, name: "Skywalker Logan",  odds: 3.7 },
    { trap: 3, name: "Toolatetosell",    odds: 4.6 },
    { trap: 4, name: "Dazzling Sunset",  odds: 6.8 },
    { trap: 5, name: "Coolavanny Aunt",  odds: 9.0 },
    { trap: 6, name: "Magical Bale",     odds: 12.0 },
  ], w: 4 },                                // mid wins → F1 L2 recovery WINS (final pop)
];

// Scenario B: "Steady Grinder" — small stake, low-odds favs, mostly clean wins.
// Outcome: small steady positive grind (~+£3 over 10 races, no recovery drama).
const RACES_GRINDER = [
  { v: "Yarmouth", d: [
    { trap: 1, name: "Coolavanny Star",  odds: 1.9 },
    { trap: 2, name: "Droopys Buzz",     odds: 2.4 },
    { trap: 3, name: "Hovex Sprite",     odds: 4.2 },
    { trap: 4, name: "Westmead Sapphire", odds: 6.0 },
    { trap: 5, name: "Skywalker Trust",  odds: 8.5 },
    { trap: 6, name: "Magical Wave",     odds: 11.0 },
  ], w: 3 },
  { v: "Sheffield", d: [
    { trap: 1, name: "Bockos Diamond",   odds: 2.0 },
    { trap: 2, name: "Romeo Forte",      odds: 2.6 },
    { trap: 3, name: "Imperial Dawn",    odds: 4.4 },
    { trap: 4, name: "Pestana Storm",    odds: 6.2 },
    { trap: 5, name: "Toolatetosell II", odds: 9.0 },
    { trap: 6, name: "Yahoo Tornado",    odds: 12.5 },
  ], w: 4 },
  { v: "Crayford", d: [
    { trap: 1, name: "Slippy Comet",     odds: 1.95 },
    { trap: 2, name: "Crash Bandit",     odds: 2.5 },
    { trap: 3, name: "Burgess Echo",     odds: 4.6 },
    { trap: 4, name: "Templeogue Bolt",  odds: 6.5 },
    { trap: 5, name: "King Apache",      odds: 8.8 },
    { trap: 6, name: "Loughteen Frost",  odds: 11.5 },
  ], w: 1 },                              // F1 wins → small loss enters L1
  { v: "Nottingham", d: [
    { trap: 1, name: "Swift Iconic",     odds: 2.1 },
    { trap: 2, name: "Newinn Cara",      odds: 2.7 },
    { trap: 3, name: "Ballyboden Spirit", odds: 4.5 },
    { trap: 4, name: "Crossfield Pulse", odds: 6.0 },
    { trap: 5, name: "Jaytee Apollo",    odds: 9.0 },
    { trap: 6, name: "Romeo Solo",       odds: 13.0 },
  ], w: 4 },                              // mid wins → F1 L1 recovery clears
  { v: "Romford", d: [
    { trap: 1, name: "Tullymurry Glow",  odds: 2.0 },
    { trap: 2, name: "Westmead Hero",    odds: 2.55 },
    { trap: 3, name: "Bockos Tempo",     odds: 4.2 },
    { trap: 4, name: "Fearless Frost",   odds: 5.8 },
    { trap: 5, name: "Toolatetosell",    odds: 9.5 },
    { trap: 6, name: "Dazzling Star",    odds: 12.0 },
  ], w: 5 },
  { v: "Sunderland", d: [
    { trap: 1, name: "Ballyboden King",  odds: 1.85 },
    { trap: 2, name: "Crossfield Wave",  odds: 2.4 },
    { trap: 3, name: "Swift Falcon",     odds: 4.4 },
    { trap: 4, name: "Jaytee Pacer",     odds: 6.5 },
    { trap: 5, name: "Romeo Mirage",     odds: 9.0 },
    { trap: 6, name: "Droopys Verve",    odds: 12.5 },
  ], w: 6 },
  { v: "Sheffield", d: [
    { trap: 1, name: "Pestana Drift",    odds: 2.05 },
    { trap: 2, name: "Newinn Dawn",      odds: 2.5 },
    { trap: 3, name: "Burgess Lightning", odds: 4.5 },
    { trap: 4, name: "Imperial Light",   odds: 6.2 },
    { trap: 5, name: "King Bandit",      odds: 9.0 },
    { trap: 6, name: "Tullymurry Wisp",  odds: 12.0 },
  ], w: 3 },
  { v: "Yarmouth", d: [
    { trap: 1, name: "Crash Brave",      odds: 1.95 },
    { trap: 2, name: "Bockos Jazz",      odds: 2.4 },
    { trap: 3, name: "Westmead Nova",    odds: 4.6 },
    { trap: 4, name: "Templeogue Joy",   odds: 6.0 },
    { trap: 5, name: "Loughteen Glow",   odds: 9.0 },
    { trap: 6, name: "Yahoo Daze",       odds: 12.5 },
  ], w: 4 },
  { v: "Romford", d: [
    { trap: 1, name: "Fearless Crown",   odds: 2.0 },
    { trap: 2, name: "Ballyboden Echo",  odds: 2.6 },
    { trap: 3, name: "Crossfield Nova",  odds: 4.2 },
    { trap: 4, name: "Swift Mirage",     odds: 6.5 },
    { trap: 5, name: "Jaytee Reign",     odds: 8.5 },
    { trap: 6, name: "Romeo Edge",       odds: 12.0 },
  ], w: 3 },
  { v: "Nottingham", d: [
    { trap: 1, name: "Slippy Onyx",      odds: 1.9 },
    { trap: 2, name: "Skywalker Pulse",  odds: 2.5 },
    { trap: 3, name: "Toolatetosell",    odds: 4.4 },
    { trap: 4, name: "Dazzling Frost",   odds: 6.5 },
    { trap: 5, name: "Coolavanny Sky",   odds: 9.0 },
    { trap: 6, name: "Magical Surge",    odds: 12.0 },
  ], w: 4 },
];

// Scenario C: "Cap Crisis" — bigger £2 stake hits the £15 liability cap and busts.
// Outcome: shows the bust-protection safety mechanism (and that you live to bet another day).
const RACES_CAP = [
  { v: "Crayford", d: [
    { trap: 1, name: "Storm Surge",      odds: 2.1 },
    { trap: 2, name: "Sky Diamond",      odds: 3.0 },
    { trap: 3, name: "Burgess Echo",     odds: 4.5 },
    { trap: 4, name: "Imperial Flash",   odds: 7.0 },
    { trap: 5, name: "King Sabre",       odds: 9.0 },
    { trap: 6, name: "Tullymurry Heat",  odds: 12.5 },
  ], w: 4 },                              // both win
  { v: "Sheffield", d: [
    { trap: 1, name: "Newinn Aura",      odds: 2.5 },
    { trap: 2, name: "Pestana Drift",    odds: 3.4 },
    { trap: 3, name: "Hovex Pulse",      odds: 4.8 },
    { trap: 4, name: "Skywalker Logan",  odds: 7.0 },
    { trap: 5, name: "Magical Bale",     odds: 9.5 },
    { trap: 6, name: "Westmead Bay",     odds: 13.0 },
  ], w: 1 },                              // F1 wins → F1 L1 (£5 stake at 2.5 odds = liability £7.50)
  { v: "Romford", d: [
    { trap: 1, name: "Fearless Crown",   odds: 2.6 },
    { trap: 2, name: "Crossfield Pulse", odds: 3.2 },
    { trap: 3, name: "Bockos Comet",     odds: 5.0 },
    { trap: 4, name: "Templeogue Bolt",  odds: 7.5 },
    { trap: 5, name: "Loughteen Frost",  odds: 9.5 },
    { trap: 6, name: "Yahoo Drift",      odds: 13.0 },
  ], w: 1 },                              // F1 wins again → F1 chain BUSTS via cap!
  { v: "Sunderland", d: [
    { trap: 1, name: "Ballyboden King",  odds: 2.4 },
    { trap: 2, name: "Crossfield Sky",   odds: 3.4 },
    { trap: 3, name: "Swift Falcon",     odds: 4.6 },
    { trap: 4, name: "Jaytee Pacer",     odds: 7.0 },
    { trap: 5, name: "Romeo Mirage",     odds: 9.0 },
    { trap: 6, name: "Droopys Verve",    odds: 12.0 },
  ], w: 5 },                              // F1 busted, only F2 active → wins
  { v: "Yarmouth", d: [
    { trap: 1, name: "Coolavanny Star",  odds: 2.6 },
    { trap: 2, name: "Droopys Buzz",     odds: 3.3 },
    { trap: 3, name: "Hovex Sprite",     odds: 4.5 },
    { trap: 4, name: "Westmead Sapphire", odds: 7.0 },
    { trap: 5, name: "Skywalker Trust",  odds: 9.0 },
    { trap: 6, name: "Magical Wave",     odds: 12.5 },
  ], w: 3 },                              // F2 also wins
  { v: "Sheffield", d: [
    { trap: 1, name: "Pestana Storm",    odds: 2.5 },
    { trap: 2, name: "Newinn Cara",      odds: 3.4 },
    { trap: 3, name: "Burgess Echo",     odds: 4.8 },
    { trap: 4, name: "Imperial Light",   odds: 6.8 },
    { trap: 5, name: "King Bandit",      odds: 9.5 },
    { trap: 6, name: "Tullymurry Heat",  odds: 13.0 },
  ], w: 4 },
  { v: "Crayford", d: [
    { trap: 1, name: "Storm Surge",      odds: 2.7 },
    { trap: 2, name: "Sky Diamond",      odds: 3.6 },
    { trap: 3, name: "Burgess Comet",    odds: 4.5 },
    { trap: 4, name: "Templeogue Bolt",  odds: 7.0 },
    { trap: 5, name: "King Sabre",       odds: 9.0 },
    { trap: 6, name: "Loughteen Frost",  odds: 12.5 },
  ], w: 5 },
  { v: "Nottingham", d: [
    { trap: 1, name: "Fearless Storm",   odds: 2.4 },
    { trap: 2, name: "Ballyboden Boss",  odds: 3.5 },
    { trap: 3, name: "Crossfield Sky",   odds: 5.0 },
    { trap: 4, name: "Swift Falcon",     odds: 7.0 },
    { trap: 5, name: "Jaytee Reign",     odds: 9.5 },
    { trap: 6, name: "Romeo Solo",       odds: 13.0 },
  ], w: 6 },
  { v: "Romford", d: [
    { trap: 1, name: "Newinn Taylor",    odds: 2.5 },
    { trap: 2, name: "Pestana Rocky",    odds: 3.4 },
    { trap: 3, name: "Burgess Bullet",   odds: 4.6 },
    { trap: 4, name: "Imperial Flash",   odds: 7.0 },
    { trap: 5, name: "King Bandit",      odds: 9.5 },
    { trap: 6, name: "Tullymurry Heat",  odds: 13.0 },
  ], w: 4 },
  { v: "Sheffield", d: [
    { trap: 1, name: "Bockos Diamond",   odds: 2.6 },
    { trap: 2, name: "Romeo Forte",      odds: 3.5 },
    { trap: 3, name: "Hovex Sprite",     odds: 4.6 },
    { trap: 4, name: "Pestana Drift",    odds: 6.8 },
    { trap: 5, name: "Westmead Hero",    odds: 9.0 },
    { trap: 6, name: "Magical Wave",     odds: 12.5 },
  ], w: 3 },
];

const SCENARIOS = [
  {
    id: "recovery",
    name: "Recovery Pop",
    desc: "Loss enters L1, drops to L2, then bounces back with a big recovery win.",
    stake: 0.5,
    startBank: 50.0,
    cap: 0,                // 0 = disabled
    races: RACES_RECOVERY,
  },
  {
    id: "grinder",
    name: "Steady Grinder",
    desc: "Low-odds favs, mostly clean wins. Small steady grind, few drawdowns.",
    stake: 1.0,
    startBank: 50.0,
    cap: 0,
    races: RACES_GRINDER,
  },
  {
    id: "cap",
    name: "Cap Crisis",
    desc: "£2 stake, £15 liability cap. Watch a chain bust safely instead of spiraling.",
    stake: 2.0,
    startBank: 50.0,
    cap: 15.0,
    races: RACES_CAP,
  },
];

// ---------- Pure simulator (mirrors backend math) ----------
const initChains = (stake) => ({
  1: { level: 0, pendingStake: stake, accumLoss: 0, busted: false },
  2: { level: 0, pendingStake: stake, accumLoss: 0, busted: false },
});

function applyRace(state, race, cfg) {
  // F1 = lowest odds, F2 = second lowest
  const sorted = [...race.d].sort((a, b) => a.odds - b.odds);
  const slots = [
    { rank: 1, runner: sorted[0] },
    { rank: 2, runner: sorted[1] },
  ];
  const chains = { ...state.chains };
  let pnlDelta = 0;
  const bets = slots.map(({ rank, runner }) => {
    const c = { ...chains[rank] };
    if (c.busted) {
      // chain is dead — skip betting but still report it as a no-op slot
      chains[rank] = c;
      return {
        rank,
        runner,
        stake: 0,
        liability: 0,
        layWon: null,
        resultPnl: 0,
        newLevel: c.level,
        capBlocked: false,
        skipped: true,
      };
    }
    const stake = c.pendingStake;
    const liability = stake * (runner.odds - 1);

    // Liability cap check (only blocks recovery bets, not initial L0)
    if (cfg.cap > 0 && c.level > 0 && liability > cfg.cap) {
      c.busted = true;
      chains[rank] = c;
      return {
        rank,
        runner,
        stake,
        liability,
        layWon: null,
        resultPnl: 0,
        newLevel: c.level,
        capBlocked: true,
        skipped: false,
      };
    }

    const layWon = runner.trap !== race.w;
    let resultPnl;
    if (layWon) {
      resultPnl = stake * (1 - COMMISSION);
      c.level = 0;
      c.pendingStake = cfg.stake;
      c.accumLoss = 0;
    } else {
      resultPnl = -liability;
      c.accumLoss += liability + stake;
      c.level += 1;
      c.pendingStake = c.accumLoss + cfg.stake;
    }
    chains[rank] = c;
    pnlDelta += resultPnl;
    return {
      rank,
      runner,
      stake,
      liability,
      layWon,
      resultPnl,
      newLevel: c.level,
      capBlocked: false,
      skipped: false,
    };
  });
  return {
    chains,
    bank: state.bank + pnlDelta,
    pnl: state.pnl + pnlDelta,
    pnlDelta,
    bets,
    winnerTrap: race.w,
    venue: race.v,
    runners: race.d,
  };
}

// ---------- Tiny presentational helpers ----------
const TRAP_COLORS = {
  1: "bg-red-500 text-white",
  2: "bg-blue-500 text-white",
  3: "bg-white text-slate-900 border border-slate-300",
  4: "bg-slate-900 text-white",
  5: "bg-amber-400 text-slate-900",
  6: "bg-slate-100 text-slate-900 border border-pink-400",
};

const StatCell = ({ label, value, tone = "white", flash = null }) => (
  <div className="bg-[#141414] border border-[#2A2A2A] p-3 relative overflow-hidden">
    <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">{label}</div>
    <div className={`font-mono font-bold text-base mt-1 ${tone}`}>{value}</div>
    {flash !== null && (
      <motion.div
        key={flash}
        initial={{ opacity: 0.45 }}
        animate={{ opacity: 0 }}
        transition={{ duration: 1 }}
        className={`absolute inset-0 ${flash >= 0 ? "bg-emerald-500" : "bg-red-500"}`}
      />
    )}
  </div>
);

const ChainPill = ({ rank, chain }) => {
  const { level, busted } = chain;
  const status = busted
    ? { cls: "bg-red-500/10 text-red-300 border-red-500/30", label: "Busted" }
    : level === 0
      ? { cls: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30", label: "Clean" }
      : { cls: "bg-amber-500/10 text-amber-300 border-amber-500/30", label: `Recovery L${level}` };
  return (
    <div className="flex items-center justify-between bg-[#141414] border border-[#2A2A2A] px-3 py-2 text-xs font-mono">
      <span className="text-pink-400 font-bold">FAV #{rank}</span>
      <span className={`px-2 py-0.5 border text-[10px] font-bold uppercase tracking-widest ${status.cls}`}>
        {status.label}
      </span>
      <span className="flex gap-0.5">
        {[1, 2, 3].map((i) => (
          <span
            key={i}
            className={`w-2 h-2 ${
              busted ? "bg-red-500/60" : i <= level ? "bg-amber-400" : "bg-[#2A2A2A]"
            }`}
          />
        ))}
      </span>
    </div>
  );
};

// ---------- The interactive demo ----------
export const InteractiveDemo = () => {
  const [scenarioIdx, setScenarioIdx] = useState(0);
  const scenario = SCENARIOS[scenarioIdx];

  const [chains, setChains] = useState(() => initChains(scenario.stake));
  const [bank, setBank] = useState(scenario.startBank);
  const [pnl, setPnl] = useState(0);
  const [history, setHistory] = useState([]);          // resolved races
  const [phase, setPhase] = useState("idle");          // idle | running | resolved | done
  const [active, setActive] = useState(null);          // {race, idx} while running
  const [latest, setLatest] = useState(null);          // last result for flash anim
  const [playing, setPlaying] = useState(true);
  const [completedSeed, setCompletedSeed] = useState(0); // bumps each loop
  const timerRef = useRef(null);

  const reset = (idx = scenarioIdx) => {
    clearTimeout(timerRef.current);
    const s = SCENARIOS[idx];
    setChains(initChains(s.stake));
    setBank(s.startBank);
    setPnl(0);
    setHistory([]);
    setPhase("idle");
    setActive(null);
    setLatest(null);
  };

  const cycleScenario = () => {
    const next = (scenarioIdx + 1) % SCENARIOS.length;
    setScenarioIdx(next);
    setPlaying(true);
    reset(next);
  };

  // Engine loop
  useEffect(() => {
    if (!playing) return;
    if (phase === "done") return;

    if (phase === "idle") {
      const nextIdx = history.length;
      if (nextIdx >= TOTAL_RACES) {
        setPhase("done");
        return;
      }
      setActive({ race: scenario.races[nextIdx], idx: nextIdx });
      setPhase("running");
      timerRef.current = setTimeout(() => {
        const result = applyRace({ chains, bank, pnl }, scenario.races[nextIdx], scenario);
        setChains(result.chains);
        setBank(result.bank);
        setPnl(result.pnl);
        setHistory((h) => [...h, { ...result, idx: nextIdx }]);
        setLatest({ delta: result.pnlDelta, idx: nextIdx });
        setPhase("resolved");
      }, RACE_DURATION_MS);
    } else if (phase === "resolved") {
      timerRef.current = setTimeout(() => {
        setActive(null);
        setPhase("idle");
      }, RESOLVE_PAUSE_MS);
    }
    // No cleanup here — the next state transition naturally replaces the timer.
  }, [phase, playing, history.length, completedSeed, scenarioIdx]); // eslint-disable-line react-hooks/exhaustive-deps

  // Pause clears any pending timer so playback truly stops.
  useEffect(() => {
    if (!playing) clearTimeout(timerRef.current);
  }, [playing]);

  // Final unmount cleanup
  useEffect(() => () => clearTimeout(timerRef.current), []);

  // auto-loop after done (3s pause then reset & re-run)
  useEffect(() => {
    if (phase !== "done") return;
    if (!playing) return;
    const t = setTimeout(() => {
      reset(scenarioIdx);
      setCompletedSeed((s) => s + 1);
    }, 3500);
    return () => clearTimeout(t);
  }, [phase, playing]); // eslint-disable-line react-hooks/exhaustive-deps

  const sparkData = useMemo(() => {
    const points = [{ x: 0, y: 0 }];
    let acc = 0;
    history.forEach((h, i) => {
      acc += h.pnlDelta;
      points.push({ x: i + 1, y: acc });
    });
    return points;
  }, [history]);

  const sortedRunners = active ? [...active.race.d].sort((a, b) => a.odds - b.odds) : [];

  return (
    <div className="relative max-w-5xl mx-auto">
      <div className="absolute -inset-2 bg-gradient-to-tr from-pink-200/60 via-pink-100/40 to-transparent rounded-3xl blur-2xl" />

      <div
        className="relative rounded-2xl border border-slate-200 bg-slate-900 shadow-2xl overflow-hidden"
        data-testid="interactive-demo"
      >
        {/* Browser chrome */}
        <div className="flex items-center gap-1.5 px-4 py-2.5 bg-slate-800 border-b border-slate-700">
          <span className="w-2.5 h-2.5 rounded-full bg-red-400/80" />
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400/80" />
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400/80" />
          <span className="ml-3 text-[11px] font-mono text-slate-400 uppercase tracking-widest">
            lay-hounds.co.uk/app — live demo
          </span>
          <div className="ml-auto flex items-center gap-1">
            <button
              data-testid="demo-cycle-scenario"
              onClick={cycleScenario}
              className="px-2.5 py-1.5 rounded text-[10px] font-mono uppercase tracking-widest font-bold bg-pink-500/10 hover:bg-pink-500/25 text-pink-300 hover:text-pink-100 border border-pink-500/30 transition-colors flex items-center gap-1.5"
              aria-label="Try a different scenario"
              title="Try a different scenario"
            >
              <Shuffle className="w-3 h-3" />
              <span className="hidden sm:inline">Try Different</span>
            </button>
            <button
              data-testid="demo-toggle-play"
              onClick={() => setPlaying((p) => !p)}
              className="p-1.5 rounded hover:bg-slate-700 text-slate-300 transition-colors"
              aria-label={playing ? "Pause" : "Play"}
            >
              {playing ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <button
              data-testid="demo-reset"
              onClick={() => reset(scenarioIdx)}
              className="p-1.5 rounded hover:bg-slate-700 text-slate-300 transition-colors"
              aria-label="Reset"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Scenario header */}
        <div
          data-testid="demo-scenario-header"
          className="bg-[#0A0A0A] border-b border-[#1A1A1A] px-4 sm:px-6 py-3 flex items-center justify-between gap-3"
        >
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-[9px] font-mono uppercase tracking-widest text-pink-400 font-bold shrink-0">
              Scenario {scenarioIdx + 1}/{SCENARIOS.length}
            </span>
            <span className="text-pink-500/40 hidden sm:inline">·</span>
            <span className="font-display font-bold text-base text-white tracking-tight truncate" data-testid="demo-scenario-name">
              {scenario.name}
            </span>
            <span className="text-[11px] text-zinc-500 hidden md:inline truncate" data-testid="demo-scenario-desc">
              — {scenario.desc}
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {SCENARIOS.map((_, i) => (
              <span
                key={i}
                className={`w-1.5 h-1.5 rounded-full transition-colors ${
                  i === scenarioIdx ? "bg-pink-500" : "bg-zinc-700"
                }`}
              />
            ))}
          </div>
        </div>

        <div className="p-4 sm:p-6 bg-[#0A0A0A] grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left: stats + chains + sparkline */}
          <div className="lg:col-span-1 space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <StatCell
                label="Bank"
                value={`£${bank.toFixed(2)}`}
                tone={bank >= scenario.startBank ? "text-emerald-400" : "text-red-400"}
                flash={latest?.idx ?? null}
              />
              <StatCell
                label="P&L"
                value={`${pnl >= 0 ? "+" : ""}£${pnl.toFixed(2)}`}
                tone={pnl >= 0 ? "text-emerald-400" : "text-red-400"}
                flash={latest?.idx ?? null}
              />
              <StatCell
                label="Race"
                value={`${history.length}/${TOTAL_RACES}`}
                tone="text-white"
              />
              <StatCell
                label="Stake"
                value={`£${scenario.stake.toFixed(2)}`}
                tone="text-white"
              />
            </div>

            <ChainPill rank={1} chain={chains[1]} />
            <ChainPill rank={2} chain={chains[2]} />

            {/* Mini sparkline */}
            <div className="bg-[#141414] border border-[#2A2A2A] p-3">
              <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 mb-2">
                Cumulative P&amp;L
              </div>
              <Sparkline data={sparkData} />
            </div>
          </div>

          {/* Right: race arena + history */}
          <div className="lg:col-span-2 space-y-3">
            <div className="bg-[#141414] border border-[#2A2A2A] p-4 min-h-[200px]">
              <AnimatePresence mode="wait">
                {phase === "running" && active && (
                  <motion.div
                    key={`running-${active.idx}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.25 }}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">
                          Race #{active.idx + 1} · {active.race.v}
                        </div>
                        <div className="font-display font-bold text-lg text-white mt-0.5">
                          Laying Fav #1 &amp; Fav #2
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-amber-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                        Running…
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      {sortedRunners.map((dog, i) => (
                        <RunnerRow key={dog.trap} dog={dog} layRank={i < 2 ? i + 1 : null} running />
                      ))}
                    </div>
                  </motion.div>
                )}

                {phase === "resolved" && history.length > 0 && (
                  <motion.div
                    key={`resolved-${history.length}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <ResolvedRaceView race={history[history.length - 1]} />
                  </motion.div>
                )}

                {phase === "done" && (
                  <motion.div
                    key="done"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="h-full flex flex-col items-center justify-center text-center py-6"
                  >
                    <Trophy className={`w-12 h-12 mb-3 ${pnl >= 0 ? "text-emerald-400" : "text-amber-400"}`} />
                    <div className="font-display font-black text-2xl text-white tracking-tight">
                      10 races complete
                    </div>
                    <div className={`font-mono text-3xl font-bold mt-2 ${pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {pnl >= 0 ? "+" : ""}£{pnl.toFixed(2)}
                    </div>
                    <div className="text-xs text-zinc-500 mt-1">looping in 3s — or open the app to run your own…</div>
                  </motion.div>
                )}

                {phase === "idle" && history.length === 0 && (
                  <motion.div
                    key="ready"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="h-full flex items-center justify-center text-zinc-500 text-sm font-mono uppercase tracking-widest"
                  >
                    Loading first race…
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Recent results strip */}
            <div className="flex gap-1 overflow-hidden">
              {Array.from({ length: TOTAL_RACES }).map((_, i) => {
                const h = history[i];
                let cls = "bg-[#1A1A1A] border-[#2A2A2A]";
                let label = "";
                if (h) {
                  cls = h.pnlDelta >= 0
                    ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                    : "bg-red-500/20 border-red-500/40 text-red-300";
                  label = h.pnlDelta >= 0 ? "+" : "";
                }
                const isCurrent = phase === "running" && active?.idx === i;
                return (
                  <div
                    key={i}
                    data-testid={`demo-race-cell-${i}`}
                    className={`flex-1 h-9 border ${cls} ${isCurrent ? "ring-2 ring-pink-500 animate-pulse" : ""} flex items-center justify-center font-mono text-[10px] font-bold transition-all`}
                  >
                    {h ? `${label}£${h.pnlDelta.toFixed(2)}` : i + 1}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* CTA bar */}
        <div className="bg-slate-800 border-t border-slate-700 px-6 py-4 flex items-center justify-between flex-wrap gap-3">
          <div className="text-xs font-mono text-slate-400 uppercase tracking-widest">
            Real algorithm · pre-scripted races for demo
          </div>
          <Link to="/app" data-testid="demo-cta-open">
            <Button className="bg-pink-500 hover:bg-pink-600 text-white px-5 py-4 rounded-lg font-semibold text-sm shadow-lg shadow-pink-500/30 hover:-translate-y-0.5 transition-all">
              Run your own configuration
              <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
};

// ---------- Sub-components ----------
const RunnerRow = ({ dog, layRank, running, winner, layWon, pnl, capBlocked, skipped }) => {
  const trapCls = TRAP_COLORS[dog.trap] || "bg-zinc-700 text-white";
  return (
    <div
      className={`flex items-center gap-2 px-2.5 py-1.5 ${
        winner ? "bg-emerald-500/10 border border-emerald-500/40"
              : "bg-[#0A0A0A] border border-[#1A1A1A]"
      }`}
    >
      <span className={`w-6 h-6 grid place-items-center font-mono font-bold text-xs ${trapCls}`}>
        {dog.trap}
      </span>
      <span className="flex-1 text-xs text-zinc-200 truncate">{dog.name}</span>
      <span className="text-xs font-mono text-zinc-400 w-14 text-right">{dog.odds.toFixed(1)}</span>
      {layRank && (
        <span className={`text-[9px] font-mono uppercase tracking-widest font-bold w-12 text-right ${
          skipped ? "text-zinc-600 line-through" : capBlocked ? "text-red-400" : "text-pink-400"
        }`}>
          {skipped ? "—" : capBlocked ? "BUST" : `LAY F${layRank}`}
        </span>
      )}
      {winner && <Trophy className="w-3.5 h-3.5 text-emerald-400 shrink-0" />}
      {!running && layRank && (
        <span
          className={`text-xs font-mono font-bold w-16 text-right ${
            skipped ? "text-zinc-600" : capBlocked ? "text-red-400" : layWon ? "text-emerald-400" : "text-red-400"
          }`}
        >
          {skipped ? "skipped" : capBlocked ? "cap-block" : `${layWon ? "+" : ""}£${pnl.toFixed(2)}`}
        </span>
      )}
    </div>
  );
};

const ResolvedRaceView = ({ race }) => {
  const sorted = [...race.runners].sort((a, b) => a.odds - b.odds);
  const layedTraps = new Set(sorted.slice(0, 2).map((d) => d.trap));
  const betByTrap = {};
  race.bets.forEach((b) => { betByTrap[b.runner.trap] = b; });

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">
            Race #{race.idx + 1} · {race.venue} — Result
          </div>
          <div className="font-display font-bold text-lg text-white mt-0.5">
            Trap {race.winnerTrap} wins
          </div>
        </div>
        <div
          className={`font-mono font-bold text-xl ${
            race.pnlDelta >= 0 ? "text-emerald-400" : "text-red-400"
          }`}
        >
          {race.pnlDelta >= 0 ? "+" : ""}£{race.pnlDelta.toFixed(2)}
        </div>
      </div>
      <div className="space-y-1.5">
        {sorted.map((dog) => {
          const bet = betByTrap[dog.trap];
          return (
            <RunnerRow
              key={dog.trap}
              dog={dog}
              layRank={layedTraps.has(dog.trap) ? (sorted[0].trap === dog.trap ? 1 : 2) : null}
              winner={dog.trap === race.winnerTrap}
              layWon={bet?.layWon}
              pnl={bet?.resultPnl ?? 0}
              capBlocked={bet?.capBlocked}
              skipped={bet?.skipped}
            />
          );
        })}
      </div>
    </div>
  );
};

const Sparkline = ({ data }) => {
  if (data.length < 2) {
    return <div className="h-12 grid place-items-center text-[10px] font-mono text-zinc-600">no data yet</div>;
  }
  const W = 200;
  const H = 48;
  const xs = data.map((p) => p.x);
  const ys = data.map((p) => p.y);
  const maxY = Math.max(0.5, ...ys);
  const minY = Math.min(-0.5, ...ys);
  const sx = (x) => (x / Math.max(...xs)) * W;
  const sy = (y) => H - ((y - minY) / (maxY - minY)) * H;
  const points = data.map((p) => `${sx(p.x)},${sy(p.y)}`).join(" ");
  const last = data[data.length - 1];
  const positive = last.y >= 0;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-12">
      <line x1="0" x2={W} y1={sy(0)} y2={sy(0)} stroke="#2A2A2A" strokeDasharray="2 3" strokeWidth="1" />
      <polyline
        points={points}
        fill="none"
        stroke={positive ? "#10B981" : "#EF4444"}
        strokeWidth="2"
      />
      <circle cx={sx(last.x)} cy={sy(last.y)} r="3" fill={positive ? "#10B981" : "#EF4444"} />
    </svg>
  );
};
