from models import LayBet, RecoveryChain, SessionConfig
from services.recovery import apply_settled_bet_to_chain, stake_for_liability_budget


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


def test_partial_recovery_win_pays_down_accumulated_loss():
    config = SessionConfig(stake=0.05, commission_rate=0.05)
    chain = RecoveryChain(level=2, pending_stake=8.0, accumulated_loss=5.0)

    apply_settled_bet_to_chain(chain, _bet(stake=2.0, level=2), config, settled_profit=1.9)

    assert chain.level == 2
    assert chain.accumulated_loss == 3.1
    assert chain.pending_stake == 3.3132
    assert chain.busted is False


def test_full_recovery_win_still_resets_chain():
    config = SessionConfig(stake=0.05, commission_rate=0.05)
    chain = RecoveryChain(level=2, pending_stake=5.3132, accumulated_loss=5.0)

    apply_settled_bet_to_chain(chain, _bet(stake=5.3132, level=2), config, settled_profit=5.0475)

    assert chain.level == 0
    assert chain.accumulated_loss == 0.0
    assert chain.pending_stake == config.stake
    assert chain.busted is False
