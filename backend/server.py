from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import random
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Literal, Any
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from betfair_client import betfair, BetfairError, EVENT_TYPE_GREYHOUND  # noqa: E402,F401

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")


# ---------- Constants ----------
INITIAL_STAKE = 0.05
TARGET_PROFIT = 0.05
MAX_RECOVERY_LEVEL = 3

UK_GREYHOUND_NAMES = [
    "Ballymac Vic", "Droopys Sydney", "Romeo Magico", "Swift Iconic",
    "Tullymurry Act", "Newinn Taylor", "Burgess Bullet", "Kilgraney Rumble",
    "Pestana Rocky", "Coolavanny Aunt", "Jaytee Yankee", "Skywalker Logan",
    "Bockos Doomie", "Hovex Bolt", "Slippy Bullet", "Droopys Verve",
    "Rough Sailor", "Magical Bale", "Fearless Storm", "Westmead Hawk",
    "Toolatetosell", "Ballyboden Boss", "Crossfield Storm", "King Turbo",
    "Swift Falcon", "Templeogue Whip", "Crash Bandicoot", "Loughteen Blanco",
    "Dazzling Sunset", "Ballyanne Sim", "Yahoo Hippy", "Imperial Spirit",
    "Roxholme Magic", "Tyrur Lewis", "Killeacle Annie", "Dancing Anto",
]


# ---------- Models ----------
class SessionConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    stake: float = INITIAL_STAKE
    num_favourites: int = Field(default=2, ge=1, le=4)
    stop_win: float = Field(default=5.0, ge=0)
    stop_loss: float = Field(default=5.0, ge=0)
    max_races: int = Field(default=20, ge=1, le=200)
    starting_bank: float = Field(default=10.0, ge=0)
    mode: Literal["simulator", "paper_live", "live"] = "simulator"
    max_liability_cap: float = Field(default=5.0, ge=0)  # live-mode safety
    risk_accepted: bool = False  # required for live mode
    commission_rate: float = Field(default=0.05, ge=0.0, le=0.2)  # Betfair typical 5%


class Greyhound(BaseModel):
    trap: int
    name: str
    odds: float
    favourite_rank: int  # 1 = favourite


class LayBet(BaseModel):
    favourite_rank: int
    dog_trap: int
    dog_name: str
    odds: float
    stake: float
    liability: float
    recovery_level: int  # 0 = initial, 1-3 = recovery levels
    result: Optional[Literal["win", "loss"]] = None  # win = lay won (dog lost)
    pnl: Optional[float] = None


class Race(BaseModel):
    race_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    race_num: int
    venue: str
    runners: List[Greyhound]
    bets: List[LayBet]
    winning_trap: int
    pnl_change: float
    bank_after: float
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: Literal["simulator", "paper_live", "live"] = "simulator"
    market_id: Optional[str] = None
    market_start_time: Optional[str] = None
    betfair_bet_ids: List[str] = Field(default_factory=list)


class RecoveryChain(BaseModel):
    """Tracks pending recovery for a specific favourite rank."""
    level: int = 0  # 0 = no active recovery (next bet is initial)
    pending_stake: float = INITIAL_STAKE  # stake to use on next race
    accumulated_loss: float = 0.0
    busted: bool = False  # True after level 3 loss; chain stopped


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    config: SessionConfig
    bank: float
    total_pnl: float = 0.0
    total_staked: float = 0.0
    total_liability_risked: float = 0.0
    races_played: int = 0
    status: Literal["active", "stopped_win", "stopped_loss", "stopped_max", "stopped_manual"] = "active"
    recovery_chains: Dict[str, RecoveryChain] = Field(default_factory=dict)  # key = str(rank)
    races: List[Race] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------- Helpers ----------
def generate_race(race_num: int) -> tuple[List[Greyhound], str]:
    venues = ["Romford", "Hove", "Nottingham", "Sheffield", "Crayford", "Towcester", "Newcastle", "Sunderland"]
    venue = random.choice(venues)
    names = random.sample(UK_GREYHOUND_NAMES, 6)
    raw_odds = []
    # Generate spread of odds: one strong fav (~1.8-3), then progressively longer
    base = random.uniform(1.8, 3.5)
    for i in range(6):
        o = round(base + i * random.uniform(0.6, 1.8) + random.uniform(-0.3, 0.6), 2)
        o = max(1.5, o)
        raw_odds.append(o)
    random.shuffle(raw_odds)  # shuffle so trap order != odds order
    # Assign trap 1..6
    runners_unsorted = [{"trap": i + 1, "name": names[i], "odds": raw_odds[i]} for i in range(6)]
    # Compute favourite rank by sorting by odds asc
    sorted_by_odds = sorted(runners_unsorted, key=lambda r: r["odds"])
    rank_by_trap = {r["trap"]: idx + 1 for idx, r in enumerate(sorted_by_odds)}
    runners = [
        Greyhound(trap=r["trap"], name=r["name"], odds=r["odds"], favourite_rank=rank_by_trap[r["trap"]])
        for r in runners_unsorted
    ]
    return runners, venue


def pick_winner(runners: List[Greyhound]) -> int:
    """Weighted random: weight = 1/odds (favourite wins more often)."""
    weights = [1.0 / r.odds for r in runners]
    total = sum(weights)
    norm = [w / total for w in weights]
    pick = random.random()
    cum = 0
    for r, w in zip(runners, norm):
        cum += w
        if pick <= cum:
            return r.trap
    return runners[-1].trap


def get_runner_by_rank(runners: List[Greyhound], rank: int) -> Greyhound:
    for r in runners:
        if r.favourite_rank == rank:
            return r
    raise ValueError(f"No runner at rank {rank}")


async def fetch_live_race() -> Dict[str, Any]:
    """Fetch next upcoming UK/IE greyhound market and convert to our race shape.

    Returns dict with: runners (List[Greyhound]), venue, market_id, market_start_time.
    """
    markets = await betfair.list_greyhound_markets(minutes_ahead=60, max_results=5)
    if not markets:
        raise HTTPException(400, "No upcoming UK/IE greyhound markets in next 60 minutes")
    # Find first market with fresh prices
    for m in markets:
        market_id = m["marketId"]
        book = await betfair.get_market_book(market_id)
        if not book:
            continue
        # Build runner rows: selectionId -> best lay price (odds we'd lay at)
        runner_meta = {r["selectionId"]: r for r in m.get("runners", [])}
        priced = []
        for br in book.get("runners", []):
            if br.get("status") != "ACTIVE":
                continue
            ex = br.get("ex", {})
            lay_prices = ex.get("availableToLay", [])
            if not lay_prices:
                continue
            odds = lay_prices[0]["price"]
            sel_id = br["selectionId"]
            meta = runner_meta.get(sel_id, {})
            priced.append({
                "selection_id": sel_id,
                "name": meta.get("runnerName", f"Runner {sel_id}"),
                "trap": int(meta.get("metadata", {}).get("CLOTH_NUMBER") or meta.get("metadata", {}).get("TRAP_NUMBER") or 0),
                "odds": float(odds),
            })
        if len(priced) < 2:
            continue
        # Assign traps if missing (use order from market)
        for i, p in enumerate(priced):
            if not p["trap"]:
                p["trap"] = i + 1
        # Compute favourite rank by ascending odds
        sorted_by_odds = sorted(priced, key=lambda r: r["odds"])
        rank_by_sel = {r["selection_id"]: idx + 1 for idx, r in enumerate(sorted_by_odds)}
        runners = [
            Greyhound(trap=p["trap"], name=p["name"], odds=round(p["odds"], 2), favourite_rank=rank_by_sel[p["selection_id"]])
            for p in priced
        ]
        # Also return selection_id mapping so live bets can target correct runner
        sel_by_rank = {rank_by_sel[p["selection_id"]]: p["selection_id"] for p in priced}
        return {
            "runners": runners,
            "venue": m.get("event", {}).get("venue") or m.get("event", {}).get("name", "Live"),
            "market_id": market_id,
            "market_start_time": m.get("marketStartTime"),
            "selection_by_rank": sel_by_rank,
        }
    raise HTTPException(400, "No markets with live prices available")


def session_to_doc(s: Session) -> dict:
    return s.model_dump()


def doc_to_session(d: dict) -> Session:
    d = {k: v for k, v in d.items() if k != "_id"}
    return Session(**d)


# ---------- Endpoints ----------
@api_router.get("/")
async def root():
    return {"message": "Greyhound Lay Simulator API"}


@api_router.post("/sessions", response_model=Session)
async def create_session(config: SessionConfig):
    if config.mode in ("paper_live", "live") and not betfair.is_configured():
        raise HTTPException(400, "Betfair credentials not configured on server")
    if config.mode == "live" and not config.risk_accepted:
        raise HTTPException(400, "Live mode requires explicit risk acceptance")
    chains = {str(i): RecoveryChain(pending_stake=config.stake) for i in range(1, config.num_favourites + 1)}
    session = Session(config=config, bank=config.starting_bank, recovery_chains=chains)
    await db.sessions.insert_one(session_to_doc(session))
    return session


@api_router.get("/sessions", response_model=List[Session])
async def list_sessions():
    docs = await db.sessions.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [Session(**d) for d in docs]


@api_router.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: str):
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    return Session(**doc)


@api_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    res = await db.sessions.delete_one({"id": session_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Session not found")
    return {"deleted": True}


@api_router.post("/sessions/{session_id}/next-race", response_model=Session)
async def next_race(session_id: str):
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    session = Session(**doc)

    if session.status != "active":
        raise HTTPException(400, f"Session is {session.status}")

    mode = session.config.mode
    market_id = None
    market_start_time = None
    selection_by_rank: Dict[int, int] = {}
    betfair_bet_ids: List[str] = []

    if mode == "simulator":
        runners, venue = generate_race(session.races_played + 1)
    else:
        live = await fetch_live_race()
        runners = live["runners"]
        venue = live["venue"]
        market_id = live["market_id"]
        market_start_time = live["market_start_time"]
        selection_by_rank = live["selection_by_rank"]

    # Place lay bets for each favourite slot
    bets: List[LayBet] = []
    for rank in range(1, session.config.num_favourites + 1):
        chain = session.recovery_chains.get(str(rank), RecoveryChain())
        if chain.busted:
            continue
        try:
            runner = get_runner_by_rank(runners, rank)
        except ValueError:
            continue
        stake = round(chain.pending_stake, 4)
        liability = round(stake * (runner.odds - 1), 4)

        # Liability cap applies to all modes — auto-busts recovery chains
        # whose next bet would exceed the safety cap.
        if session.config.max_liability_cap > 0 and liability > session.config.max_liability_cap:
            chain.busted = True
            continue

        bets.append(LayBet(
            favourite_rank=rank, dog_trap=runner.trap, dog_name=runner.name,
            odds=runner.odds, stake=stake, liability=liability,
            recovery_level=chain.level,
        ))

        if mode == "live":
            try:
                sel_id = selection_by_rank[rank]
                result = await betfair.place_lay_bet(market_id, sel_id, runner.odds, stake)
                for rep in result.get("instructionReports", []):
                    if rep.get("betId"):
                        betfair_bet_ids.append(rep["betId"])
            except BetfairError as e:
                raise HTTPException(502, f"Betfair bet placement failed: {e}")

    # Live mode: bet placed on real Betfair, no simulated settlement
    if mode == "live":
        race = Race(
            race_num=session.races_played + 1, venue=venue, runners=runners,
            bets=bets, winning_trap=0, pnl_change=0.0, bank_after=session.bank,
            source=mode, market_id=market_id, market_start_time=market_start_time,
            betfair_bet_ids=betfair_bet_ids,
        )
        session.races_played += 1
        session.races.append(race)
        await db.sessions.replace_one({"id": session_id}, session_to_doc(session))
        return session

    # Simulator + paper_live: simulate outcome
    winning_trap = pick_winner(runners)

    pnl_change = 0.0
    total_staked = 0.0
    total_liability = 0.0
    for bet in bets:
        chain = session.recovery_chains[str(bet.favourite_rank)]
        total_staked += bet.stake
        total_liability += bet.liability
        if bet.dog_trap == winning_trap:
            bet.result = "loss"
            bet.pnl = -bet.liability
            pnl_change -= bet.liability
            new_accum = chain.accumulated_loss + bet.liability + bet.stake
            if chain.level >= MAX_RECOVERY_LEVEL:
                chain.busted = True
                chain.level = MAX_RECOVERY_LEVEL
                chain.pending_stake = session.config.stake
                chain.accumulated_loss = new_accum
            else:
                chain.level += 1
                chain.accumulated_loss = new_accum
                chain.pending_stake = round(bet.liability + bet.stake + session.config.stake, 4)
        else:
            bet.result = "win"
            gross_win = bet.stake
            commission = round(gross_win * session.config.commission_rate, 4)
            net_win = round(gross_win - commission, 4)
            bet.pnl = net_win
            pnl_change += net_win
            chain.level = 0
            chain.accumulated_loss = 0.0
            chain.pending_stake = session.config.stake

    session.bank = round(session.bank + pnl_change, 4)
    session.total_pnl = round(session.total_pnl + pnl_change, 4)
    session.total_staked = round(session.total_staked + total_staked, 4)
    session.total_liability_risked = round(session.total_liability_risked + total_liability, 4)
    session.races_played += 1

    race = Race(
        race_num=session.races_played, venue=venue, runners=runners, bets=bets,
        winning_trap=winning_trap, pnl_change=round(pnl_change, 4),
        bank_after=session.bank, source=mode, market_id=market_id,
        market_start_time=market_start_time,
    )
    session.races.append(race)

    if session.total_pnl >= session.config.stop_win:
        session.status = "stopped_win"
    elif session.total_pnl <= -session.config.stop_loss:
        session.status = "stopped_loss"
    elif session.races_played >= session.config.max_races:
        session.status = "stopped_max"

    await db.sessions.replace_one({"id": session_id}, session_to_doc(session))
    return session


@api_router.get("/betfair/status")
async def betfair_status():
    return await betfair.status()


@api_router.get("/bank/current")
async def current_bank():
    """Return the ending bank of the most recent session, or None if no sessions exist."""
    doc = await db.sessions.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    if not doc:
        return {"bank": None}
    return {"bank": doc.get("bank", 0.0), "from_session_id": doc.get("id"), "status": doc.get("status")}


@api_router.get("/daily-stats")
async def daily_stats():
    """Aggregate P&L per session (each session = one trading day)."""
    docs = await db.sessions.find({}, {"_id": 0}).sort("created_at", 1).to_list(500)
    rows = []
    cumulative = 0.0
    for d in docs:
        pnl = d.get("total_pnl", 0.0)
        cumulative += pnl
        rows.append({
            "id": d["id"],
            "created_at": d.get("created_at"),
            "pnl": round(pnl, 2),
            "cumulative_pnl": round(cumulative, 2),
            "bank_start": d.get("config", {}).get("starting_bank", 0.0),
            "bank_end": d.get("bank", 0.0),
            "races": d.get("races_played", 0),
            "status": d.get("status", "active"),
            "mode": d.get("config", {}).get("mode", "simulator"),
        })
    return {"days": rows, "total_pnl": round(cumulative, 2), "sessions": len(rows)}


class CapPreviewInput(BaseModel):
    stake: float = Field(ge=0.01)
    max_liability_cap: float = Field(ge=0)
    num_favourites: int = Field(default=2, ge=1, le=4)
    commission_rate: float = Field(default=0.05, ge=0, le=0.2)
    iterations: int = Field(default=2000, ge=100, le=10000)


@api_router.post("/preview-cap")
async def preview_cap(inp: CapPreviewInput):
    """Monte-Carlo preview of cap impact for given stake/cap.
    Runs `iterations` independent race chains per favourite rank.
    Returns bust-level distribution, expected profit/race, worst chain loss.
    """

    def simulate_one_rank():
        """Simulate one chain-life on a given rank until it resets (win) or busts."""
        level = 0
        pending = inp.stake
        accum_loss = 0.0
        chain_pnl = 0.0
        races = 0
        # Loop races until chain resets to L0 via a win, or busts.
        for _ in range(10):
            runners, _v = generate_race(1)
            runner = get_runner_by_rank(runners, 1)  # treat as rank-1 surrogate
            odds = runner.odds
            liability = pending * (odds - 1)
            if inp.max_liability_cap > 0 and liability > inp.max_liability_cap:
                return {"bust_level": level, "chain_pnl": -accum_loss, "races": races}
            races += 1
            winner = pick_winner(runners)
            if winner == runner.trap:
                # lay loses
                chain_pnl -= liability
                accum_loss += liability + pending
                if level >= MAX_RECOVERY_LEVEL:
                    return {"bust_level": MAX_RECOVERY_LEVEL, "chain_pnl": chain_pnl, "races": races}
                level += 1
                pending = liability + pending + inp.stake
            else:
                gross = pending
                commission = gross * inp.commission_rate
                chain_pnl += gross - commission
                return {"won_at_level": level, "chain_pnl": chain_pnl, "races": races}
        return {"bust_level": level, "chain_pnl": chain_pnl, "races": races}

    # Restore default random for simulation determinism
    _seed = random.getstate()
    random.seed(42)
    try:
        stats = {"bust_L0": 0, "bust_L1": 0, "bust_L2": 0, "bust_L3": 0,
                 "won_L0": 0, "won_L1": 0, "won_L2": 0, "won_L3": 0}
        total_pnl = 0.0
        total_races = 0
        worst_chain = 0.0
        for _ in range(inp.iterations):
            res = simulate_one_rank()
            total_pnl += res["chain_pnl"]
            total_races += res["races"]
            worst_chain = min(worst_chain, res["chain_pnl"])
            if "won_at_level" in res:
                stats[f"won_L{res['won_at_level']}"] += 1
            else:
                stats[f"bust_L{res['bust_level']}"] += 1
    finally:
        random.setstate(_seed)

    chains_total = inp.iterations
    wins = stats["won_L0"] + stats["won_L1"] + stats["won_L2"] + stats["won_L3"]
    busts = chains_total - wins
    bust_at_L0 = stats["bust_L0"]  # capped before placing any bet
    reach_L3 = stats["won_L3"] + stats["bust_L3"]

    return {
        "iterations": chains_total,
        "per_rank": inp.num_favourites,
        "win_rate": round(wins / chains_total * 100, 1),
        "bust_rate": round(busts / chains_total * 100, 1),
        "reach_l3_rate": round(reach_L3 / chains_total * 100, 1),
        "bust_distribution": {
            "L0_cap_blocked": bust_at_L0,
            "L1": stats["bust_L1"],
            "L2": stats["bust_L2"],
            "L3": stats["bust_L3"],
        },
        "win_distribution": {
            "L0": stats["won_L0"], "L1": stats["won_L1"],
            "L2": stats["won_L2"], "L3": stats["won_L3"],
        },
        "expected_profit_per_race": round(total_pnl / max(total_races, 1) * inp.num_favourites, 4),
        "worst_chain_loss": round(worst_chain, 2),
    }


@api_router.get("/betfair/races")
async def betfair_races(minutes_ahead: int = 30, max_results: int = 10):
    try:
        markets = await betfair.list_greyhound_markets(minutes_ahead=minutes_ahead, max_results=max_results)
    except BetfairError as e:
        raise HTTPException(502, f"Betfair error: {e}")
    return {"count": len(markets), "markets": markets}


@api_router.post("/sessions/{session_id}/stop", response_model=Session)
async def stop_session(session_id: str):
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    session = Session(**doc)
    if session.status == "active":
        session.status = "stopped_manual"
        await db.sessions.replace_one({"id": session_id}, session_to_doc(session))
    return session


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
