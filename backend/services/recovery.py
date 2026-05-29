from models import LayBet, RecoveryChain, SessionConfig


def target_net_profit(config: SessionConfig) -> float:
    return round(config.stake * (1 - config.commission_rate), 4)


def stake_for_shortfall(shortfall: float, config: SessionConfig) -> float:
    net_factor = max(1 - config.commission_rate, 0.0001)
    return round((shortfall + target_net_profit(config)) / net_factor, 4)


def apply_settled_bet_to_chain(
    chain: RecoveryChain,
    bet: LayBet,
    config: SessionConfig,
    settled_profit: float,
) -> None:
    """Update a recovery chain from one settled lay bet.

    The chain tracks shortfall versus the expected per-selection net profit.
    That means a losing bet adds both the actual loss and the missed target
    profit, so the next recovery bet can catch up the race profit curve.
    """
    target = target_net_profit(config)

    if settled_profit < 0:
        base_level = max(chain.level, bet.recovery_level)
        shortfall = round(chain.accumulated_loss + abs(settled_profit) + target, 4)
        if base_level >= config.max_recovery_level:
            chain.busted = True
            chain.level = config.max_recovery_level
            chain.pending_stake = config.stake
            chain.accumulated_loss = shortfall
            return
        chain.level = base_level + 1
        chain.accumulated_loss = shortfall
        chain.pending_stake = stake_for_shortfall(shortfall, config)
        return

    if chain.accumulated_loss <= 0:
        chain.level = 0
        chain.accumulated_loss = 0.0
        chain.pending_stake = config.stake
        chain.busted = False
        return

    surplus_after_current_target = max(settled_profit - target, 0.0)
    remaining = round(chain.accumulated_loss - surplus_after_current_target, 4)
    if remaining <= 0.0001:
        chain.level = 0
        chain.accumulated_loss = 0.0
        chain.pending_stake = config.stake
        chain.busted = False
        return

    chain.level = max(chain.level, bet.recovery_level)
    chain.accumulated_loss = remaining
    chain.pending_stake = stake_for_shortfall(remaining, config)
