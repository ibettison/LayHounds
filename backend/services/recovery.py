import logging
from dataclasses import dataclass
from typing import Optional

from models import LayBet, RecoveryChain, SessionConfig

logger = logging.getLogger(__name__)


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


def _money(value: float) -> float:
    return round(max(value, 0.0), 4)


def target_net_profit(config: SessionConfig) -> float:
    return round(config.stake * (1 - config.commission_rate), 4)


def recovery_total(chain: RecoveryChain) -> float:
    _sync_legacy_balance(chain)
    return _money(chain.normal_recovery_balance + chain.overflow_recovery_balance)


def _sync_legacy_balance(chain: RecoveryChain) -> None:
    if (
        chain.accumulated_loss > 0
        and chain.normal_recovery_balance == 0
        and chain.overflow_recovery_balance == 0
    ):
        chain.normal_recovery_balance = _money(chain.accumulated_loss)
    chain.accumulated_loss = _money(chain.normal_recovery_balance + chain.overflow_recovery_balance)


def is_chain_back_to_green(chain: RecoveryChain, session_profit: float) -> bool:
    return recovery_total(chain) <= 0


def stake_for_shortfall(shortfall: float, config: SessionConfig) -> float:
    return stake_for_recovery_balance(shortfall + target_net_profit(config), config)


def stake_for_recovery_balance(balance: float, config: SessionConfig) -> float:
    net_factor = max(1 - config.commission_rate, 0.0001)
    if balance <= 0:
        return round(config.stake, 4)
    return round(balance / net_factor, 4)


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
    """Return the safely capped bet and retain any unpaid recovery in overflow."""
    _sync_legacy_balance(chain)

    recovery_before = recovery_total(chain)
    desired_recovery = recovery_before
    desired_stake = stake_for_recovery_balance(recovery_before, config)
    desired_liability = round(desired_stake * (odds - 1), 4)
    stake = desired_stake
    liability = desired_liability
    capped_by_stop_loss = False
    capped_by_liability = False

    if stop_loss_budget is not None and liability > stop_loss_budget:
        stake = stake_for_liability_budget(odds, stop_loss_budget)
        liability = round(stake * (odds - 1), 4)
        capped_by_stop_loss = True

    if config.max_liability_cap > 0 and liability > config.max_liability_cap:
        stake = stake_for_liability_budget(odds, config.max_liability_cap)
        liability = round(stake * (odds - 1), 4)
        capped_by_liability = True

    stake = _money(stake)
    liability = _money(liability)
    was_capped = capped_by_stop_loss or capped_by_liability
    unpaid = 0.0

    if was_capped and recovery_before > 0:
        capped_net_profit = _money(stake * (1 - config.commission_rate))
        recoverable_now = min(recovery_before, capped_net_profit)
        unpaid = _money(recovery_before - recoverable_now)
        chain.normal_recovery_balance = _money(recoverable_now)
        chain.overflow_recovery_balance = unpaid
        _sync_legacy_balance(chain)

    logger.info(
        "Recovery bet plan: recovery_before=%.4f desired_recovery=%.4f "
        "desired_liability=%.4f capped_liability=%.4f unpaid_moved_to_overflow=%.4f "
        "normal_recovery=%.4f overflow_recovery=%.4f was_capped=%s",
        recovery_before,
        desired_recovery,
        desired_liability,
        liability if was_capped else 0.0,
        unpaid,
        chain.normal_recovery_balance,
        chain.overflow_recovery_balance,
        was_capped,
    )

    return RecoveryBetPlan(
        stake=stake,
        liability=liability,
        recovery_before=recovery_before,
        desired_recovery=desired_recovery,
        desired_liability=desired_liability,
        capped_liability=liability if was_capped else 0.0,
        unpaid_moved_to_overflow=unpaid,
        was_capped=was_capped,
    )


def refresh_pending_stake(chain: RecoveryChain, config: SessionConfig) -> None:
    _sync_legacy_balance(chain)
    total = recovery_total(chain)
    chain.pending_stake = stake_for_recovery_balance(total, config)
    if total <= 0:
        chain.pending_stake = config.stake


def apply_settled_bet_to_chain(
    chain: RecoveryChain,
    bet: LayBet,
    config: SessionConfig,
    settled_profit: float,
    *,
    session_profit: float = 0.0,
) -> None:
    """Update a recovery chain from one settled lay bet."""
    _sync_legacy_balance(chain)

    if settled_profit < 0:
        base_level = max(chain.level, bet.recovery_level)
        missed_target = target_net_profit(config)
        new_recovery = _money(abs(settled_profit) + missed_target)
        chain.normal_recovery_balance = _money(chain.normal_recovery_balance + new_recovery)
        if base_level >= config.max_recovery_level:
            chain.busted = True
            chain.level = config.max_recovery_level
        else:
            chain.level = base_level + 1
        refresh_pending_stake(chain, config)
        logger.info(
            "Recovery settlement loss: pnl=%.4f added_recovery=%.4f "
            "normal_after=%.4f overflow_after=%.4f genuinely_back_to_green=%s",
            settled_profit,
            new_recovery,
            chain.normal_recovery_balance,
            chain.overflow_recovery_balance,
            is_chain_back_to_green(chain, session_profit),
        )
        return

    remaining_profit = _money(settled_profit)
    normal_paid = min(chain.normal_recovery_balance, remaining_profit)
    chain.normal_recovery_balance = _money(chain.normal_recovery_balance - normal_paid)
    remaining_profit = _money(remaining_profit - normal_paid)
    overflow_paid = min(chain.overflow_recovery_balance, remaining_profit)
    chain.overflow_recovery_balance = _money(chain.overflow_recovery_balance - overflow_paid)
    refresh_pending_stake(chain, config)
    back_to_green = is_chain_back_to_green(chain, session_profit)
    if back_to_green:
        chain.level = 0
        chain.busted = False
        chain.pending_stake = config.stake
    elif recovery_total(chain) > 0:
        chain.level = max(chain.level, 1, bet.recovery_level)
    else:
        chain.level = max(chain.level, 1, bet.recovery_level)
        chain.pending_stake = config.stake

    logger.info(
        "Recovery settlement win: pnl=%.4f normal_after=%.4f overflow_after=%.4f "
        "genuinely_back_to_green=%s",
        settled_profit,
        chain.normal_recovery_balance,
        chain.overflow_recovery_balance,
        back_to_green,
    )
