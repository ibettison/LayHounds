from models import LayBet, RecoveryChain, SessionConfig
from services.recovery import (
    apply_settled_bet_to_chain,
    plan_recovery_bet,
    recovery_total,
    stake_for_liability_budget,
)


def _bet(stake=1.0, liability=2.0, level=1, result="win"):
    return LayBet(
        favourite_rank=1,
        dog_trap=1,
        dog_name="Test Runner",
        odds=3.0,
        stake=stake,
        liability=liability,
        recovery_level=level,
        result=result,
    )


def test_stake_for_liability_budget_keeps_liability_inside_budget():
    stake = stake_for_liability_budget(3.5, 5.0)

    assert stake == 2.0
    assert round(stake * (3.5 - 1), 4) <= 5.0


def test_loss_adds_liability_plus_missed_target_to_normal_balance():
    config = SessionConfig(stake=0.05, commission_rate=0.05)
    chain = RecoveryChain()

    apply_settled_bet_to_chain(
        chain,
        _bet(liability=1.0, level=0, result="loss"),
        config,
        settled_profit=-1.0,
        session_profit=-1.0,
    )

    assert chain.normal_recovery_balance == 1.0475
    assert chain.overflow_recovery_balance == 0.0
    assert chain.accumulated_loss == 1.0475
    assert chain.level == 1


def test_recovery_bet_below_max_liability_is_not_moved_to_overflow():
    config = SessionConfig(stake=0.05, commission_rate=0.05, max_liability_cap=5.0)
    chain = RecoveryChain(level=1, normal_recovery_balance=1.0475)

    plan = plan_recovery_bet(chain, odds=2.0, config=config, stop_loss_budget=100.0)

    assert plan.was_capped is False
    assert plan.unpaid_moved_to_overflow == 0.0
    assert chain.normal_recovery_balance == 1.0475
    assert chain.overflow_recovery_balance == 0.0
    assert round(plan.stake * 0.95, 4) == 1.0475


def test_recovery_bet_above_max_liability_moves_unpaid_to_overflow():
    config = SessionConfig(stake=0.05, commission_rate=0.05, max_liability_cap=2.0)
    chain = RecoveryChain(level=2, normal_recovery_balance=10.0)

    plan = plan_recovery_bet(chain, odds=3.0, config=config, stop_loss_budget=100.0)

    assert plan.was_capped is True
    assert plan.capped_liability == 2.0
    assert chain.normal_recovery_balance == 0.95
    assert chain.overflow_recovery_balance == 9.05
    assert plan.unpaid_moved_to_overflow == 9.05
    assert recovery_total(chain) == 10.0


def test_recovery_bet_above_stop_loss_moves_unpaid_to_overflow():
    config = SessionConfig(stake=0.05, commission_rate=0.05, max_liability_cap=0)
    chain = RecoveryChain(level=2, normal_recovery_balance=10.0)

    plan = plan_recovery_bet(chain, odds=3.0, config=config, stop_loss_budget=1.0)

    assert plan.was_capped is True
    assert plan.capped_liability == 1.0
    assert chain.normal_recovery_balance == 0.475
    assert chain.overflow_recovery_balance == 9.525
    assert plan.unpaid_moved_to_overflow == 9.525


def test_multiple_capped_recovery_bets_keep_spreading_overflow():
    config = SessionConfig(stake=0.05, commission_rate=0.05, max_liability_cap=2.0)
    chain = RecoveryChain(level=2, normal_recovery_balance=10.0)

    first = plan_recovery_bet(chain, odds=3.0, config=config, stop_loss_budget=100.0)
    apply_settled_bet_to_chain(
        chain,
        _bet(stake=first.stake, liability=first.liability, level=2),
        config,
        settled_profit=0.95,
        session_profit=-9.05,
    )
    second = plan_recovery_bet(chain, odds=3.0, config=config, stop_loss_budget=100.0)

    assert second.was_capped is True
    assert chain.normal_recovery_balance == 0.95
    assert chain.overflow_recovery_balance == 8.1
    assert recovery_total(chain) == 9.05


def test_winning_capped_recovery_partially_clears_normal_first():
    config = SessionConfig(stake=0.05, commission_rate=0.05, max_liability_cap=2.0)
    chain = RecoveryChain(level=2, normal_recovery_balance=10.0)
    plan = plan_recovery_bet(chain, odds=3.0, config=config, stop_loss_budget=100.0)

    apply_settled_bet_to_chain(
        chain,
        _bet(stake=plan.stake, liability=plan.liability, level=2),
        config,
        settled_profit=0.5,
        session_profit=-9.5,
    )

    assert chain.normal_recovery_balance == 0.45
    assert chain.overflow_recovery_balance == 9.05
    assert chain.level >= 1


def test_winning_full_recovery_clears_both_balances_when_session_green():
    config = SessionConfig(stake=0.05, commission_rate=0.05, max_liability_cap=0)
    chain = RecoveryChain(level=2, normal_recovery_balance=1.0, overflow_recovery_balance=2.0)

    apply_settled_bet_to_chain(
        chain,
        _bet(stake=3.1579, liability=4.0, level=2),
        config,
        settled_profit=3.0,
        session_profit=0.25,
    )

    assert chain.normal_recovery_balance == 0.0
    assert chain.overflow_recovery_balance == 0.0
    assert chain.accumulated_loss == 0.0
    assert chain.level == 0
    assert chain.pending_stake == config.stake


def test_winning_recovery_keeps_chasing_own_chain_shortfall():
    config = SessionConfig(stake=0.05, commission_rate=0.05, max_liability_cap=0)
    chain = RecoveryChain(level=3, normal_recovery_balance=5.0)

    apply_settled_bet_to_chain(
        chain,
        _bet(stake=3.1684, liability=2.0, level=3),
        config,
        settled_profit=3.01,
        session_profit=-1.99,
    )

    assert chain.level == 3
    assert chain.normal_recovery_balance == 1.99
    assert chain.overflow_recovery_balance == 0.0
    assert chain.accumulated_loss == 1.99
    assert round(chain.pending_stake * 0.95, 4) == 1.99


def test_winning_recovery_does_not_inherit_other_chains_session_shortfall():
    config = SessionConfig(stake=0.05, commission_rate=0.05, max_liability_cap=0)
    chain = RecoveryChain(level=3, normal_recovery_balance=1.0)

    apply_settled_bet_to_chain(
        chain,
        _bet(stake=1.0526, liability=2.0, level=3),
        config,
        settled_profit=1.0,
        session_profit=-1.99,
    )

    assert chain.level == 0
    assert chain.normal_recovery_balance == 0.0
    assert chain.overflow_recovery_balance == 0.0
    assert chain.accumulated_loss == 0.0
    assert chain.pending_stake == config.stake


def test_losing_capped_recovery_adds_new_loss_without_wiping_overflow():
    config = SessionConfig(stake=0.05, commission_rate=0.05, max_liability_cap=2.0, max_recovery_level=5)
    chain = RecoveryChain(level=2, normal_recovery_balance=10.0)
    plan = plan_recovery_bet(chain, odds=3.0, config=config, stop_loss_budget=100.0)

    apply_settled_bet_to_chain(
        chain,
        _bet(stake=plan.stake, liability=plan.liability, level=2, result="loss"),
        config,
        settled_profit=-2.0,
        session_profit=-12.0,
    )

    assert chain.normal_recovery_balance == 2.9975
    assert chain.overflow_recovery_balance == 9.05
    assert recovery_total(chain) == 12.0475
