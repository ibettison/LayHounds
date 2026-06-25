from models import LayBet, RecoveryChain, SessionConfig
from services.recovery import (
    apply_settled_bet_to_chain,
    plan_recovery_bet,
    recovery_total,
    stake_for_liability_budget,
)


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


def test_elastic_recovery_caps_liability_and_uses_debt_band():
    config = SessionConfig(
        stake=0.05,
        commission_rate=0.05,
        recovery_mode="elastic",
        max_liability_cap=75,
    )
    chain = RecoveryChain(level=3, accumulated_loss=40.0, outstanding_debt=40.0)

    plan = plan_recovery_bet(chain, 10.0, config)

    assert plan.recovery_percentage == 0.25
    assert plan.recovery_state == "CAPITAL PRESERVATION"
    assert plan.liability <= 75
    assert plan.was_capped is True


def test_elastic_recovery_win_reduces_debt_and_steps_level_down():
    config = SessionConfig(stake=0.05, commission_rate=0.05, recovery_mode="elastic")
    chain = RecoveryChain(level=3, accumulated_loss=20.0, outstanding_debt=20.0)
    bet = _bet(stake=10.0, level=3)

    apply_settled_bet_to_chain(chain, bet, config, settled_profit=9.5)

    assert chain.level == 2
    assert chain.outstanding_debt == 10.5
    assert chain.recovery_percentage == 0.75
    assert chain.recovery_state == "CONTROLLED RECOVERY"
    assert bet.outstanding_debt_after == 10.5
