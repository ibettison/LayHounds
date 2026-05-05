from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import random
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Literal
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

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
    chains = {str(i): RecoveryChain() for i in range(1, config.num_favourites + 1)}
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

    # Generate race
    runners, venue = generate_race(session.races_played + 1)

    # Place lay bets for each favourite slot
    bets: List[LayBet] = []
    for rank in range(1, session.config.num_favourites + 1):
        chain = session.recovery_chains.get(str(rank), RecoveryChain())
        if chain.busted:
            continue  # skip busted chains
        runner = get_runner_by_rank(runners, rank)
        stake = round(chain.pending_stake, 4)
        liability = round(stake * (runner.odds - 1), 4)
        bets.append(LayBet(
            favourite_rank=rank,
            dog_trap=runner.trap,
            dog_name=runner.name,
            odds=runner.odds,
            stake=stake,
            liability=liability,
            recovery_level=chain.level,
        ))

    # Pick winner
    winning_trap = pick_winner(runners)

    # Settle bets and update chains
    pnl_change = 0.0
    total_staked = 0.0
    total_liability = 0.0
    for bet in bets:
        chain = session.recovery_chains[str(bet.favourite_rank)]
        total_staked += bet.stake
        total_liability += bet.liability
        if bet.dog_trap == winning_trap:
            # Lay LOSES — laid dog won
            bet.result = "loss"
            bet.pnl = -bet.liability
            pnl_change -= bet.liability
            new_accum = chain.accumulated_loss + bet.liability + bet.stake
            if chain.level >= MAX_RECOVERY_LEVEL:
                # Already at level 3, this loss busts the chain
                chain.busted = True
                chain.level = MAX_RECOVERY_LEVEL
                chain.pending_stake = INITIAL_STAKE  # not used
                chain.accumulated_loss = new_accum
            else:
                chain.level += 1
                chain.accumulated_loss = new_accum
                # Next stake recovers liability + stake + target profit
                chain.pending_stake = round(bet.liability + bet.stake + TARGET_PROFIT, 4)
        else:
            # Lay WINS — laid dog lost
            bet.result = "win"
            bet.pnl = bet.stake
            pnl_change += bet.stake
            chain.level = 0
            chain.accumulated_loss = 0.0
            chain.pending_stake = INITIAL_STAKE

    session.bank = round(session.bank + pnl_change, 4)
    session.total_pnl = round(session.total_pnl + pnl_change, 4)
    session.total_staked = round(session.total_staked + total_staked, 4)
    session.total_liability_risked = round(session.total_liability_risked + total_liability, 4)
    session.races_played += 1

    race = Race(
        race_num=session.races_played,
        venue=venue,
        runners=runners,
        bets=bets,
        winning_trap=winning_trap,
        pnl_change=round(pnl_change, 4),
        bank_after=session.bank,
    )
    session.races.append(race)

    # Check stop conditions
    if session.total_pnl >= session.config.stop_win:
        session.status = "stopped_win"
    elif session.total_pnl <= -session.config.stop_loss:
        session.status = "stopped_loss"
    elif session.races_played >= session.config.max_races:
        session.status = "stopped_max"

    await db.sessions.replace_one({"id": session_id}, session_to_doc(session))
    return session


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
