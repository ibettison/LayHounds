from dataclasses import dataclass
from typing import Optional

from models import LayBet, RecoveryChain, SessionConfig


@dataclass(frozen=True)
class RecoveryBetPlan:
    stake: float
    liability: float
    recovery_before: float
    desired_recovery: float
    desired_liability: float
    capped_liability: float
    unpaid_moved_to_overflow: float
    was_capped: bool


def target_net_profit(config: SessionConfig) -> float:
    return round(config.stake * (1 - config.commission_rate), 4)


def recovery_total(chain: RecoveryChain) -> float:
    return round(max(chain.accumulated_loss, 0.0), 4)


def stake_for_shortfall(shortfall: float, config: SessionConfig) -> float:
    net_factor = max(1 - config.commission_rate, 0.0001)
    return round((shortfall + target_net_profit(config)) / net_factor, 4)


def stake_for_liability_budget(odds: float, liability_budget: float) -> float:
    if odds <= 1 or liability_budget <= 0:
        return 0.0
    return round(liability_budget / (odds - 1), 4)


def plan_recovery_bet(
    chain: RecoveryChain,
    odds: float,
    config: SessionConfig,
    *,
    stop_loss_budget: Optional[float] = None,
) -> RecoveryBetPlan:
    stake = round(chain.pending_stake, 4)
    liability = round(stake * (odds - 1), 4)
    capped_liability = 0.0
    was_capped = False

    if stop_loss_budget is not None and liability > stop_loss_budget:
        stake = stake_for_liability_budget(odds, stop_loss_budget)
        liability = round(stake * (odds - 1), 4)
        capped_liability = liability
        was_capped = True

    return RecoveryBetPlan(
        stake=stake,
        liability=liability,
        recovery_before=recovery_total(chain),
        desired_recovery=recovery_total(chain),
        desired_liability=round(chain.pending_stake * (odds - 1), 4),
        capped_liability=capped_liability,
        unpaid_moved_to_overflow=0.0,
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
    if settled_profit < 0:
        base_level = max(chain.level, bet.recovery_level)
        shortfall = round(chain.accumulated_loss + abs(settled_profit), 4)
        if base_level >= config.max_recovery_level:
            chain.busted = True
            chain.level = config.max_recovery_level
            chain.pending_stake = config.stake
            chain.accumulated_loss = shortfall
            return
        chain.level = base_level + 1
        chain.accumulated_loss = shortfall
        chain.normal_recovery_balance = 0.0
        chain.overflow_recovery_balance = 0.0
        chain.pending_stake = stake_for_shortfall(shortfall, config)
        return

    remaining_shortfall = round(max(chain.accumulated_loss - settled_profit, 0.0), 4)
    if remaining_shortfall > 0:
        chain.level = max(chain.level, bet.recovery_level, 1)
        chain.accumulated_loss = remaining_shortfall
        chain.normal_recovery_balance = 0.0
        chain.overflow_recovery_balance = 0.0
        chain.pending_stake = stake_for_shortfall(remaining_shortfall, config)
        chain.busted = False
        return

    chain.level = 0
    chain.accumulated_loss = 0.0
    chain.normal_recovery_balance = 0.0
    chain.overflow_recovery_balance = 0.0
    chain.pending_stake = config.stake
    chain.busted = False
