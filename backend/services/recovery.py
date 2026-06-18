from models import LayBet, RecoveryChain, SessionConfig


def target_net_profit(config: SessionConfig) -> float:
    return round(config.stake * (1 - config.commission_rate), 4)


def stake_for_shortfall(shortfall: float, config: SessionConfig) -> float:
    net_factor = max(1 - config.commission_rate, 0.0001)
    return round((shortfall + target_net_profit(config)) / net_factor, 4)


def stake_for_liability_budget(odds: float, liability_budget: float) -> float:
    if odds <= 1 or liability_budget <= 0:
        return 0.0
    return round(liability_budget / (odds - 1), 4)


def apply_settled_bet_to_chain(
    chain: RecoveryChain,
    bet: LayBet,
    config: SessionConfig,
    settled_profit: float,
) -> None:
    """Update a recovery chain from one settled lay bet.

    The chain tracks the actual money lost on that favourite rank. The next
    recovery stake aims to clear that deficit and add one normal target profit,
    instead of backfilling a target for every skipped/losing race.
    """
    target = target_net_profit(config)

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
        chain.pending_stake = stake_for_shortfall(shortfall, config)
        return

    chain.level = 0
    chain.accumulated_loss = 0.0
    chain.pending_stake = config.stake
    chain.busted = False
