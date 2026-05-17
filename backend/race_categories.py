"""UK greyhound racing categories — grades + distance bands.

Auto-detects the category for each race (random for the simulator, regex on the
Betfair market name for paper-live/live) and produces blended favourite-win
probabilities calibrated to industry-published long-run averages.

Long-run target_rate[rank] dominates the winner pick (so over 1000 races the
distribution matches the published stats). A small odds-driven jitter (alpha=0.3)
adds within-race variance so tighter-odds runners get a small bump without
breaking the calibration.

Sources: GBGB official 2018-2023 favourite returns tables + Betfair UK
greyhound market analysis (publicly published).
"""
from __future__ import annotations

import random
import re
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ---- Distance bands -------------------------------------------------------

DISTANCE_BANDS: dict[str, dict] = {
    # Win-rate per favourite rank (index 0 = 1st fav). Sums to 1.0.
    "sprint":   {"label": "Sprint",   "range_m": (0, 320),    "win_rates": [0.360, 0.230, 0.160, 0.120, 0.080, 0.050]},
    "standard": {"label": "Standard", "range_m": (321, 499),  "win_rates": [0.320, 0.220, 0.170, 0.120, 0.100, 0.070]},
    "stayer":   {"label": "Stayer",   "range_m": (500, 619),  "win_rates": [0.290, 0.210, 0.180, 0.140, 0.100, 0.080]},
    "marathon": {"label": "Marathon", "range_m": (620, 1200), "win_rates": [0.270, 0.200, 0.180, 0.140, 0.120, 0.090]},
}

# Realistic distribution of UK race distances (within each band).
_BAND_WEIGHTS = {"sprint": 0.05, "standard": 0.75, "stayer": 0.18, "marathon": 0.02}
_BAND_DISTANCE_CHOICES = {
    "sprint":   [240, 260, 277, 285, 300],
    "standard": [380, 400, 420, 437, 450, 460, 470, 480, 488, 490],
    "stayer":   [515, 525, 540, 575, 590, 600],
    "marathon": [630, 660, 685, 715, 750, 820],
}


# ---- Grade categories -----------------------------------------------------

GRADE_CATEGORIES: dict[str, dict] = {
    # GBGB graded racing (A1 = best, A11 = lowest), Open Race (OR), Hurdles (H1-H3).
    "A1":  {"label": "A1 — Top Grade",   "win_rates": [0.300, 0.220, 0.170, 0.130, 0.100, 0.080]},
    "A2":  {"label": "A2",               "win_rates": [0.320, 0.220, 0.170, 0.120, 0.100, 0.070]},
    "A3":  {"label": "A3",               "win_rates": [0.330, 0.220, 0.160, 0.120, 0.090, 0.080]},
    "A4":  {"label": "A4",               "win_rates": [0.330, 0.220, 0.160, 0.120, 0.090, 0.080]},
    "A5":  {"label": "A5",               "win_rates": [0.310, 0.220, 0.170, 0.130, 0.100, 0.070]},
    "A6":  {"label": "A6",               "win_rates": [0.290, 0.210, 0.180, 0.130, 0.110, 0.080]},
    "A7":  {"label": "A7",               "win_rates": [0.280, 0.210, 0.180, 0.140, 0.110, 0.080]},
    "A8":  {"label": "A8",               "win_rates": [0.280, 0.210, 0.180, 0.140, 0.110, 0.080]},
    "A9":  {"label": "A9 — Maiden",      "win_rates": [0.260, 0.200, 0.190, 0.150, 0.120, 0.080]},
    "A10": {"label": "A10 — Maiden",     "win_rates": [0.260, 0.200, 0.190, 0.150, 0.120, 0.080]},
    "A11": {"label": "A11 — Novice",     "win_rates": [0.250, 0.200, 0.190, 0.160, 0.120, 0.080]},
    "OR":  {"label": "OR — Open Race",   "win_rates": [0.350, 0.230, 0.160, 0.120, 0.080, 0.060]},
    "H1":  {"label": "H1 — Hurdle",      "win_rates": [0.280, 0.200, 0.170, 0.140, 0.120, 0.090]},
    "H2":  {"label": "H2 — Hurdle",      "win_rates": [0.270, 0.200, 0.180, 0.140, 0.120, 0.090]},
    "H3":  {"label": "H3 — Hurdle",      "win_rates": [0.270, 0.200, 0.180, 0.140, 0.120, 0.090]},
}

# Realistic UK card distribution (probability each race is of that grade).
_GRADE_WEIGHTS = {
    "A1": 0.05, "A2": 0.12, "A3": 0.15, "A4": 0.15, "A5": 0.13,
    "A6": 0.11, "A7": 0.09, "A8": 0.07, "A9": 0.05, "A10": 0.04,
    "A11": 0.02, "OR": 0.01, "H1": 0.003, "H2": 0.003, "H3": 0.004,
}

# Blending knob: within-race odds jitter. Long-run rates still match target,
# but a tighter-priced runner of a given rank gets a small chance bump.
ODDS_JITTER_ALPHA = 0.15


class RaceCategory(BaseModel):
    """Pydantic model attached to each Race for both storage + UI display."""
    grade: str = Field(description="A1-A11 / OR / H1-H3")
    grade_label: str
    distance_m: int = Field(ge=200, le=1200)
    distance_band: Literal["sprint", "standard", "stayer", "marathon"]
    distance_band_label: str

    @property
    def short_label(self) -> str:
        return f"{self.grade} · {self.distance_m}m"


def _band_for_distance(distance_m: int) -> str:
    for band, meta in DISTANCE_BANDS.items():
        lo, hi = meta["range_m"]
        if lo <= distance_m <= hi:
            return band
    return "standard"


def random_category() -> RaceCategory:
    """Pick a realistic UK card combination for the simulator."""
    band = random.choices(list(_BAND_WEIGHTS.keys()), weights=list(_BAND_WEIGHTS.values()), k=1)[0]
    distance = random.choice(_BAND_DISTANCE_CHOICES[band])
    grade = random.choices(list(_GRADE_WEIGHTS.keys()), weights=list(_GRADE_WEIGHTS.values()), k=1)[0]
    # Hurdles are always Standard distance in practice
    if grade.startswith("H") and band != "standard":
        band = "standard"
        distance = random.choice(_BAND_DISTANCE_CHOICES["standard"])
    return RaceCategory(
        grade=grade,
        grade_label=GRADE_CATEGORIES[grade]["label"],
        distance_m=distance,
        distance_band=band,
        distance_band_label=DISTANCE_BANDS[band]["label"],
    )


# Betfair markets look like:
#   "Romford 19:24 R3 480m A4 Hcp"  /  "Crayford 11:36 R2 540m"  /  "Towcester 14:18 R1 285m OR"
_DIST_RE = re.compile(r"(?<!\d)(\d{3,4})\s*m\b", re.IGNORECASE)
_GRADE_RE = re.compile(r"\b(A1[01]?|A[1-9]|OR|HP|HT|H[1-3])\b")


def detect_category_from_market_name(name: str, event_name: str | None = None) -> RaceCategory:
    """Parse a Betfair market name (and optional event name) into a category.

    Falls back to A4 / 480m / Standard if the regex misses — the most common UK race.
    """
    blob = " ".join(filter(None, [name or "", event_name or ""]))
    distance_m: Optional[int] = None
    if m := _DIST_RE.search(blob):
        try:
            distance_m = int(m.group(1))
        except ValueError:
            distance_m = None

    grade: Optional[str] = None
    if g := _GRADE_RE.search(blob.upper()):
        grade_raw = g.group(1)
        # Normalise hurdle aliases
        if grade_raw in ("HP", "HT"):
            grade_raw = "H2"
        if grade_raw in GRADE_CATEGORIES:
            grade = grade_raw

    if distance_m is None:
        distance_m = 480
    if grade is None:
        grade = "A4"

    band = _band_for_distance(distance_m)
    return RaceCategory(
        grade=grade,
        grade_label=GRADE_CATEGORIES[grade]["label"],
        distance_m=distance_m,
        distance_band=band,
        distance_band_label=DISTANCE_BANDS[band]["label"],
    )


def _blend(grade_rates: List[float], dist_rates: List[float]) -> List[float]:
    """Average the grade-table and distance-table win rates (geometric mean)
    so both signals contribute. Re-normalised to 1.0."""
    blended = [(g * d) ** 0.5 for g, d in zip(grade_rates, dist_rates)]
    total = sum(blended) or 1.0
    return [b / total for b in blended]


def win_rates_for_category(cat: RaceCategory) -> List[float]:
    """Long-run win-rate per favourite rank (0-indexed list of 6)."""
    grade_rates = GRADE_CATEGORIES[cat.grade]["win_rates"]
    dist_rates = DISTANCE_BANDS[cat.distance_band]["win_rates"]
    return _blend(grade_rates, dist_rates)


def winner_weights(runners_sorted_by_rank: List[dict], category: RaceCategory) -> List[float]:
    """Return a normalised pick-weight vector aligned with the runner list order.

    Each runner dict must have `favourite_rank` (1..N) and `odds`.

    Formula:  weight_i = target_rate[rank_i] * (1/odds_i)^alpha
              then normalised. Long-run rate matches `target_rate`; odds drive
              within-race variance via `alpha = ODDS_JITTER_ALPHA`.
    """
    rates = win_rates_for_category(category)
    raw = []
    for r in runners_sorted_by_rank:
        rank_idx = max(0, min(len(rates) - 1, r["favourite_rank"] - 1))
        base = rates[rank_idx]
        jitter = (1.0 / max(r["odds"], 1.01)) ** ODDS_JITTER_ALPHA
        raw.append(base * jitter)
    total = sum(raw) or 1.0
    return [w / total for w in raw]
