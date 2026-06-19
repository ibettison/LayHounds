from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from statistics import mean

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from models import LayBet, RecoveryChain, Session, SessionConfig  # noqa: E402
from services.favourite_risk import favourite_risk_bet_plan  # noqa: E402
from services.historical_replay import BUNDLED_REPLAY_PACK, _load_replay_pack_days  # noqa: E402
from services.racing import get_runner_by_rank  # noqa: E402
from services.recovery import apply_settled_bet_to_chain, recovery_total, stake_for_liability_budget  # noqa: E402
from services.session_status import apply_stop_conditions  # noqa: E402

STAKES = [0.05, 0.50, 1.00, 1.50, 2.00]
STOP_WIN_MULTIPLES = [10, 20, 40, 80]
STOP_LOSS_MULTIPLES = [20, 40, 80, 160]
LIABILITY_CAP_MULTIPLE = 100
MAX_RACES = 200
NUM_FAVOURITES = 2
MAX_RECOVERY_LEVEL = 3
COMMISSION_RATE = 0.05
STARTING_BANK_MULTIPLE = 200

OUT_DIR = PROJECT_DIR / "test_reports"
CSV_PATH = OUT_DIR / "historical-replay-stake-stop-grid.csv"
REPORT_PATH = OUT_DIR / "historical-replay-stake-stop-report.md"


def floor_money(value: float) -> float:
    return int(max(value, 0.0) * 10000) / 10000


def money(value: float) -> str:
    return f"£{value:,.2f}"


def pct(value: int, total: int) -> float:
    return round((value / total) * 100, 1) if total else 0.0


def remaining_stop_loss_budget(session: Session) -> float:
    if session.config.stop_loss <= 0:
        return 0.0
    return round(max(session.config.stop_loss + session.total_pnl, 0.0), 4)


def simulate_day(day_key: str, races: list, config: SessionConfig) -> dict:
    session = Session(
        config=config,
        bank=config.starting_bank,
        recovery_chains={
            str(i): RecoveryChain(pending_stake=config.stake)
            for i in range(1, config.num_favourites + 1)
        },
        historical_replay_day=day_key,
    )
    peak = 0.0
    max_drawdown = 0.0
    bets_placed = 0
    races_with_bets = 0
    guard_skips = 0
    cap_busts = 0
    recovery_busts = 0

    for race in races:
        if session.status != "active":
            break
        if session.races_played >= config.max_races:
            apply_stop_conditions(session)
            if session.status != "active":
                break

        bet_ranks, risk_reasons = favourite_risk_bet_plan(
            race.runners,
            config,
            distance_m=race.category.distance_m if race.category else None,
        )
        if risk_reasons:
            guard_skips += 1

        bets: list[LayBet] = []
        overrun_mode = session.races_played >= config.max_races
        for rank in bet_ranks:
            chain = session.recovery_chains.setdefault(str(rank), RecoveryChain(pending_stake=config.stake))
            if chain.busted or (overrun_mode and chain.level == 0):
                continue
            try:
                runner = get_runner_by_rank(race.runners, rank)
            except ValueError:
                continue
            if runner.odds < config.odds_min or runner.odds > config.odds_max:
                continue

            stake = round(chain.pending_stake, 4)
            liability = round(stake * (runner.odds - 1), 4)
            loss_budget = remaining_stop_loss_budget(session)
            if liability > loss_budget:
                stake = floor_money(stake_for_liability_budget(runner.odds, loss_budget))
                liability = round(stake * (runner.odds - 1), 4)
            if stake <= 0 or liability <= 0:
                continue
            if config.max_liability_cap > 0 and liability > config.max_liability_cap:
                chain.busted = True
                cap_busts += 1
                continue

            bets.append(
                LayBet(
                    favourite_rank=rank,
                    dog_trap=runner.trap,
                    dog_name=runner.name,
                    odds=runner.odds,
                    stake=stake,
                    liability=liability,
                    recovery_level=chain.level,
                )
            )

        if not bets:
            session.races_played += 1
            apply_stop_conditions(session)
            continue

        races_with_bets += 1
        gross_pnl = 0.0
        for bet in bets:
            bets_placed += 1
            if bet.dog_trap == race.winning_trap:
                bet.result = "loss"
                bet.pnl = -bet.liability
                gross_pnl -= bet.liability
            else:
                bet.result = "win"
                bet.pnl = bet.stake
                gross_pnl += bet.stake

        commission = round(max(gross_pnl, 0.0) * race.commission_rate, 4)
        winners = [bet for bet in bets if bet.result == "win" and (bet.pnl or 0) > 0]
        total_winning_gross = sum(bet.pnl or 0.0 for bet in winners)
        if commission > 0 and total_winning_gross > 0:
            allocated = 0.0
            for idx, bet in enumerate(winners):
                if idx == len(winners) - 1:
                    share = round(commission - allocated, 4)
                else:
                    share = round(commission * ((bet.pnl or 0.0) / total_winning_gross), 4)
                    allocated = round(allocated + share, 4)
                bet.pnl = round((bet.pnl or 0.0) - share, 4)

        pnl_change = round(sum(bet.pnl or 0.0 for bet in bets), 4)
        projected_profit = round(session.total_pnl + pnl_change, 4)
        before_busted = {rank: session.recovery_chains[str(rank)].busted for rank in range(1, config.num_favourites + 1)}
        for bet in bets:
            apply_settled_bet_to_chain(
                session.recovery_chains[str(bet.favourite_rank)],
                bet,
                config,
                bet.pnl or 0.0,
                session_profit=projected_profit,
            )
        for rank in range(1, config.num_favourites + 1):
            if session.recovery_chains[str(rank)].busted and not before_busted[rank]:
                recovery_busts += 1

        session.total_pnl = round(session.total_pnl + pnl_change, 4)
        session.bank = round(session.bank + pnl_change, 4)
        session.races_played += 1
        peak = max(peak, session.total_pnl)
        max_drawdown = max(max_drawdown, round(peak - session.total_pnl, 4))
        apply_stop_conditions(session)

    return {
        "day": day_key,
        "status": session.status,
        "pnl": round(session.total_pnl, 4),
        "positive": session.total_pnl > 0,
        "races_processed": session.races_played,
        "races_with_bets": races_with_bets,
        "bets_placed": bets_placed,
        "max_drawdown": round(max_drawdown, 4),
        "open_recovery": round(sum(recovery_total(c) for c in session.recovery_chains.values()), 4),
        "cap_busts": cap_busts,
        "recovery_busts": recovery_busts,
        "guard_skips": guard_skips,
    }


def summarise(stake: float, stop_win: float, stop_loss: float, liability_cap: float, day_results: list[dict]) -> dict:
    total_days = len(day_results)
    total_pnl = round(sum(result["pnl"] for result in day_results), 4)
    best_day = max(day_results, key=lambda result: result["pnl"])
    worst_day = min(day_results, key=lambda result: result["pnl"])
    row = {
        "stake": stake,
        "stop_win": stop_win,
        "stop_loss": stop_loss,
        "liability_cap": liability_cap,
        "days_tested": total_days,
        "positive_days": sum(1 for result in day_results if result["positive"]),
        "stopped_win_days": sum(1 for result in day_results if result["status"] == "stopped_win"),
        "stopped_loss_days": sum(1 for result in day_results if result["status"] == "stopped_loss"),
        "stopped_max_days": sum(1 for result in day_results if result["status"] == "stopped_max"),
        "total_pnl": total_pnl,
        "avg_pnl_per_day": round(total_pnl / max(total_days, 1), 4),
        "median_pnl_day": sorted(result["pnl"] for result in day_results)[total_days // 2],
        "best_day": best_day["day"],
        "best_day_pnl": best_day["pnl"],
        "worst_day": worst_day["day"],
        "worst_day_pnl": worst_day["pnl"],
        "avg_max_drawdown": round(mean(result["max_drawdown"] for result in day_results), 4),
        "bets_placed": sum(result["bets_placed"] for result in day_results),
        "cap_busts": sum(result["cap_busts"] for result in day_results),
        "recovery_busts": sum(result["recovery_busts"] for result in day_results),
    }
    row["positive_day_rate_pct"] = pct(row["positive_days"], total_days)
    row["stopped_win_rate_pct"] = pct(row["stopped_win_days"], total_days)
    row["stopped_loss_rate_pct"] = pct(row["stopped_loss_days"], total_days)
    row["_score"] = (
        row["total_pnl"] > 0,
        row["positive_days"],
        row["stopped_win_days"],
        row["total_pnl"],
        -row["stopped_loss_days"],
        -row["cap_busts"],
        -row["recovery_busts"],
    )
    return row


def write_report(rows: list[dict], day_count: int, race_count: int) -> None:
    lines = [
        "# Historical Replay Stake / Stop Grid Report",
        "",
        f"Generated from bundled Historical Replay pack `{BUNDLED_REPLAY_PACK.name}`: {day_count} days, {race_count} races.",
        "",
        "## Method",
        "",
        "- Each historical day is treated as one replay session, processed in market-time order.",
        f"- Stakes tested: {', '.join(money(stake) for stake in STAKES)}.",
        f"- Stop-win values are scaled by stake: x{', x'.join(str(value) for value in STOP_WIN_MULTIPLES)}.",
        f"- Stop-loss values are scaled by stake: x{', x'.join(str(value) for value in STOP_LOSS_MULTIPLES)}.",
        f"- Max liability cap is scaled by stake: x{LIABILITY_CAP_MULTIPLE}.",
        f"- Other settings: {NUM_FAVOURITES} favourites, strict favourite-risk guard, max recovery L{MAX_RECOVERY_LEVEL}, max {MAX_RACES} races.",
        "- Ranking priority: positive total P&L, positive days, stopped-win days, total P&L, fewer stopped-loss days, fewer busts.",
        "",
        "## Best Overall Positive P&L Combinations",
        "",
        "| Rank | Stake | Stop Win | Stop Loss | Liability Cap | Positive Days | Stop-Win Days | Stop-Loss Days | Total P&L | Avg/Day | Worst Day | Cap Busts | Recovery Busts |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    profitable_rows = [row for row in rows if row["total_pnl"] > 0]
    for idx, row in enumerate(profitable_rows[:20], start=1):
        lines.append(
            f"| {idx} | {money(row['stake'])} | {money(row['stop_win'])} | {money(row['stop_loss'])} | {money(row['liability_cap'])} "
            f"| {row['positive_days']}/{row['days_tested']} ({row['positive_day_rate_pct']}%) | {row['stopped_win_days']} | {row['stopped_loss_days']} "
            f"| {money(row['total_pnl'])} | {money(row['avg_pnl_per_day'])} | {money(row['worst_day_pnl'])} | {row['cap_busts']} | {row['recovery_busts']} |"
        )

    lines.extend(
        [
            "",
            "## Best Combination By Stake",
            "",
            "| Stake | Stop Win | Stop Loss | Liability Cap | Positive Days | Stop-Win Days | Stop-Loss Days | Total P&L | Avg/Day | Best Day | Worst Day |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for stake in STAKES:
        row = next(row for row in rows if row["stake"] == stake)
        lines.append(
            f"| {money(stake)} | {money(row['stop_win'])} | {money(row['stop_loss'])} | {money(row['liability_cap'])} "
            f"| {row['positive_days']}/{row['days_tested']} ({row['positive_day_rate_pct']}%) | {row['stopped_win_days']} | {row['stopped_loss_days']} "
            f"| {money(row['total_pnl'])} | {money(row['avg_pnl_per_day'])} | {row['best_day']} {money(row['best_day_pnl'])} | {row['worst_day']} {money(row['worst_day_pnl'])} |"
        )

    best = profitable_rows[0] if profitable_rows else rows[0]
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- Best ranked setting: stake {money(best['stake'])}, stop win {money(best['stop_win'])}, stop loss {money(best['stop_loss'])}, liability cap {money(best['liability_cap'])}.",
            f"- It finished positive on {best['positive_days']} of {best['days_tested']} historical days and produced {money(best['total_pnl'])} over the replay pack.",
            "- The CSV contains the full grid so the result can be filtered by stake, stop-win, stop-loss, P&L, drawdown and bust count.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    days = _load_replay_pack_days(BUNDLED_REPLAY_PACK)
    day_items = [(day, days[day]) for day in sorted(days)]
    rows: list[dict] = []

    for stake in STAKES:
        liability_cap = round(stake * LIABILITY_CAP_MULTIPLE, 2)
        for stop_win_multiple in STOP_WIN_MULTIPLES:
            for stop_loss_multiple in STOP_LOSS_MULTIPLES:
                stop_win = round(stake * stop_win_multiple, 2)
                stop_loss = round(stake * stop_loss_multiple, 2)
                config = SessionConfig(
                    mode="simulator",
                    stake=stake,
                    num_favourites=NUM_FAVOURITES,
                    stop_win=stop_win,
                    stop_loss=stop_loss,
                    max_races=MAX_RACES,
                    starting_bank=round(stake * STARTING_BANK_MULTIPLE, 2),
                    max_liability_cap=liability_cap,
                    commission_rate=COMMISSION_RATE,
                    max_recovery_level=MAX_RECOVERY_LEVEL,
                    favourite_risk_guard="strict",
                )
                day_results = [simulate_day(day, races, config) for day, races in day_items]
                rows.append(summarise(stake, stop_win, stop_loss, liability_cap, day_results))

    rows.sort(key=lambda row: row["_score"], reverse=True)
    fields = [field for field in rows[0] if field != "_score"]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})
    write_report(rows, len(day_items), sum(len(races) for _, races in day_items))

    print(
        json.dumps(
            {
                "days": len(day_items),
                "races": sum(len(races) for _, races in day_items),
                "combinations": len(rows),
                "csv": str(CSV_PATH),
                "report": str(REPORT_PATH),
                "best": {key: value for key, value in rows[0].items() if key != "_score"},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
