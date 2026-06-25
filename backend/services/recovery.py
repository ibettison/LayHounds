from dataclasses import dataclass
from typing import Optional

from models import LayBet, RecoveryChain, SessionConfig


@dataclass(frozen=True)
class RecoveryBetPlan:
    stake: float
    liability: float
    recovery_before: float
    recovery_percentage: float
    recovery_state: str
    desired_recovery: float
    desired_liability: float
    capped_liability: float
    unpaid_moved_to_overflow: float
    was_capped: bool


def target_net_profit(config: SessionConfig) -> float:
    return round(config.stake * (1 - config.commission_rate), 4)


def recovery_total(chain: RecoveryChain) -> float:
    return round(max(chain.outstanding_debt or chain.accumulated_loss, 0.0), 4)


def stake_for_shortfall(shortfall: float, config: SessionConfig) -> float:
    net_factor = max(1 - config.commission_rate, 0.0001)
    return round((shortfall + target_net_profit(config)) / net_factor, 4)


def stake_for_liability_budget(odds: float, liability_budget: float) -> float:
    if odds <= 1 or liability_budget <= 0:
        return 0.0
    return round(liability_budget / (odds - 1), 4)


def recovery_chain_type(rank: int) -> str:
    if rank == 1:
        return "favourite"
    if rank == 2:
        return "second_favourite"
    return "rank"


def elastic_recovery_percentage(debt: float) -> float:
    if debt < 5:
        return 1.0
    if debt < 15:
        return 0.75
    if debt < 30:
        return 0.50
    return 0.25


def recovery_state_for_percentage(percentage: float) -> str:
    if percentage >= 1.0:
        return "NORMAL RECOVERY"
    if percentage >= 0.75:
        return "CONTROLLED RECOVERY"
    if percentage >= 0.50:
        return "DEFENSIVE RECOVERY"
    return "CAPITAL PRESERVATION"


def recovery_percentage_for_chain(chain: RecoveryChain, config: SessionConfig) -> float:
    if getattr(config, "recovery_mode", "current") != "elastic":
        return 1.0
    return elastic_recovery_percentage(recovery_total(chain))


def recovery_stake_for_chain(chain: RecoveryChain, config: SessionConfig) -> float:
    debt = recovery_total(chain)
    if debt <= 0:
        return round(config.stake, 4)
    percentage = recovery_percentage_for_chain(chain, config)
    return stake_for_shortfall(round(debt * percentage, 4), config)


def refresh_chain_projection(chain: RecoveryChain, config: SessionConfig, *, odds: Optional[float] = None) -> None:
    debt = recovery_total(chain)
    percentage = recovery_percentage_for_chain(chain, config)
    chain.outstanding_debt = debt
    chain.accumulated_loss = debt
    chain.recovery_percentage = percentage
    chain.recovery_state = recovery_state_for_percentage(percentage)
    chain.pending_stake = recovery_stake_for_chain(chain, config)
    chain.max_liability_allowed = round(config.max_liability_cap, 4)
    if odds is not None:
        chain.current_liability = round(chain.pending_stake * (odds - 1), 4)


def plan_recovery_bet(
    chain: RecoveryChain,
    odds: float,
    config: SessionConfig,
    *,
    stop_loss_budget: Optional[float] = None,
) -> RecoveryBetPlan:
    refresh_chain_projection(chain, config, odds=odds)
    desired_stake = round(chain.pending_stake, 4)
    stake = desired_stake
    liability = round(stake * (odds - 1), 4)
    capped_liability = 0.0
    was_capped = False

    if stop_loss_budget is not None and liability > stop_loss_budget:
        stake = stake_for_liability_budget(odds, stop_loss_budget)
        liability = round(stake * (odds - 1), 4)
        capped_liability = liability
        was_capped = True

    if (
        getattr(config, "recovery_mode", "current") == "elastic"
        and config.max_liability_cap > 0
        and liability > config.max_liability_cap
    ):
        stake = stake_for_liability_budget(odds, config.max_liability_cap)
        liability = round(stake * (odds - 1), 4)
        capped_liability = liability
        was_capped = True

    return RecoveryBetPlan(
        stake=stake,
        liability=liability,
        recovery_before=recovery_total(chain),
        recovery_percentage=chain.recovery_percentage,
        recovery_state=chain.recovery_state,
        desired_recovery=round(recovery_total(chain) * chain.recovery_percentage, 4),
        desired_liability=round(desired_stake * (odds - 1), 4),
        capped_liability=capped_liability,
        unpaid_moved_to_overflow=max(round(round(desired_stake * (odds - 1), 4) - liability, 4), 0.0),
        was_capped=was_capped,
    )


def apply_settled_bet_to_chain(
    chain: RecoveryChain,
    bet: LayBet,
    config: SessionConfig,
    settled_profit: float,
    *,
    session_profit: float = 0.0,
) -> None:
    """Update a recovery chain from one settled lay bet.

    The chain tracks the actual money lost on that favourite rank. The next
    recovery stake aims to clear that deficit and add one normal target profit,
    instead of backfilling a target for every skipped/losing race.
    """
    chain.outstanding_debt = recovery_total(chain)
    if settled_profit < 0:
        base_level = max(chain.level, bet.recovery_level)
        shortfall = round(recovery_total(chain) + abs(settled_profit), 4)
        if base_level >= config.max_recovery_level:
            chain.busted = True
            chain.level = config.max_recovery_level
            chain.pending_stake = config.stake
            chain.accumulated_loss = shortfall
            chain.outstanding_debt = shortfall
            chain.normal_recovery_balance = shortfall
            chain.overflow_recovery_balance = 0.0
            chain.current_liability = 0.0
            bet.outstanding_debt_after = shortfall
            return
        chain.level = base_level + 1
        chain.accumulated_loss = shortfall
        chain.outstanding_debt = shortfall
        chain.normal_recovery_balance = shortfall
        chain.overflow_recovery_balance = 0.0
        chain.busted = False
        refresh_chain_projection(chain, config)
        bet.outstanding_debt_after = chain.outstanding_debt
        return

    remaining_shortfall = round(max(recovery_total(chain) - settled_profit, 0.0), 4)
    if remaining_shortfall > 0:
        chain.level = max(chain.level - 1, 1) if getattr(config, "recovery_mode", "current") == "elastic" else max(chain.level, bet.recovery_level, 1)
        chain.accumulated_loss = remaining_shortfall
        chain.outstanding_debt = remaining_shortfall
        chain.normal_recovery_balance = remaining_shortfall
        chain.overflow_recovery_balance = 0.0
        chain.busted = False
        refresh_chain_projection(chain, config)
        bet.outstanding_debt_after = chain.outstanding_debt
        return

    chain.level = 0
    chain.accumulated_loss = 0.0
    chain.outstanding_debt = 0.0
    chain.normal_recovery_balance = 0.0
    chain.overflow_recovery_balance = 0.0
    chain.pending_stake = config.stake
    chain.recovery_percentage = 1.0
    chain.recovery_state = "NORMAL RECOVERY"
    chain.current_liability = 0.0
    chain.busted = False
    bet.outstanding_debt_after = 0.0
