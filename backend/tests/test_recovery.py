from models import LayBet, RecoveryChain, SessionConfig
from services.recovery import apply_settled_bet_to_chain, recovery_total, stake_for_liability_budget


def _bet(stake=1.0, liability=2.0, level=1):
    return LayBet(
        favourite_rank=1,
        dog_trap=1,
        dog_name="Test Runner",
        odds=3.0,
        stake=stake,
        liability=liability,
        recovery_level=level,
    )


def test_stake_for_liability_budget_keeps_liability_inside_budget():
    stake = stake_for_liability_budget(3.5, 5.0)

    assert stake == 2.0
    assert round(stake * (3.5 - 1), 4) <= 5.0


def test_loss_adds_actual_loss_to_accumulated_loss():
    config = SessionConfig(stake=0.05, commission_rate=0.05)
    chain = RecoveryChain()

    apply_settled_bet_to_chain(chain, _bet(liability=1.0, level=0), config, settled_profit=-1.0)

    assert chain.level == 1
    assert chain.accumulated_loss == 1.0
    assert round(chain.pending_stake * 0.95, 4) == 1.0475
    assert recovery_total(chain) == 1.0
    assert chain.busted is False


def test_full_recovery_win_resets_chain():
    config = SessionConfig(stake=0.05, commission_rate=0.05)
    chain = RecoveryChain(level=2, pending_stake=5.3132, accumulated_loss=5.0)

    apply_settled_bet_to_chain(chain, _bet(stake=5.3132, level=2), config, settled_profit=5.0475)

    assert chain.level == 0
    assert chain.accumulated_loss == 0.0
    assert chain.normal_recovery_balance == 0.0
    assert chain.overflow_recovery_balance == 0.0
    assert chain.pending_stake == config.stake
    assert chain.busted is False


def test_partial_recovery_win_carries_own_chain_shortfall():
    config = SessionConfig(stake=0.05, commission_rate=0.05)
    chain = RecoveryChain(level=3, pending_stake=5.3132, accumulated_loss=5.0)

    apply_settled_bet_to_chain(
        chain,
        _bet(stake=3.1684, level=3),
        config,
        settled_profit=3.01,
        session_profit=-1.99,
    )

    assert chain.level == 3
    assert chain.accumulated_loss == 1.99
    assert round(chain.pending_stake * 0.95, 4) == 2.0375
    assert chain.busted is False


def test_recovery_win_does_not_inherit_other_chains_session_shortfall():
    config = SessionConfig(stake=0.05, commission_rate=0.05)
    chain = RecoveryChain(level=3, pending_stake=1.0526, accumulated_loss=1.0)

    apply_settled_bet_to_chain(
        chain,
        _bet(stake=1.0526, level=3),
        config,
        settled_profit=1.0,
        session_profit=-1.99,
    )

    assert chain.level == 0
    assert chain.accumulated_loss == 0.0
    assert chain.pending_stake == config.stake
    assert chain.busted is False


def test_losing_at_max_recovery_level_busts_chain_without_wiping_loss():
    config = SessionConfig(stake=0.05, commission_rate=0.05, max_recovery_level=3)
    chain = RecoveryChain(level=3, pending_stake=5.3132, accumulated_loss=5.0)

    apply_settled_bet_to_chain(chain, _bet(level=3), config, settled_profit=-2.0)

    assert chain.level == 3
    assert chain.accumulated_loss == 7.0
    assert chain.pending_stake == config.stake
    assert chain.busted is True
