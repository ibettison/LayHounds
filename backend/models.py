from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from race_categories import RaceCategory

INITIAL_STAKE = 0.05
TARGET_PROFIT = 0.05

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
    odds_min: float = Field(default=1.01, ge=1.01, le=1000.0)  # only lay favs with odds >=
    odds_max: float = Field(default=1000.0, ge=1.01, le=1000.0)  # and <=
    max_recovery_level: int = Field(default=3, ge=1, le=5)  # configurable depth of recovery staircase
    auto_place: bool = False  # live mode: auto-fire bet 60s before next race start


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
    # Real Betfair-side data, populated immediately after placeOrders and
    # updated again on settlement so the UI shows actual matched figures
    # instead of intended ones.
    betfair_bet_id: Optional[str] = None
    matched_size: Optional[float] = None        # actual size matched (£)
    matched_price: Optional[float] = None       # weighted average price matched
    placement_status: Optional[str] = None      # 'matched' | 'unmatched' | 'partial' | 'placed' | 'settled'
    betfair_status: Optional[str] = None
    settled_profit: Optional[float] = None
    settled_at: Optional[str] = None
    # Signed Betfair-tick delta between the requested odds and the actual matched
    # price. Positive = price drifted out (BAD for LAY — more liability).
    # Negative = price steamed in (GOOD for LAY).
    slippage_ticks: Optional[int] = None


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
    category: Optional[RaceCategory] = None


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


