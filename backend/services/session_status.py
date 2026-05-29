from models import Session


def apply_stop_conditions(session: Session, *, allow_recovery_overrun: bool = True) -> None:
    if session.total_pnl >= session.config.stop_win:
        session.status = "stopped_win"
        return
    if session.total_pnl <= -session.config.stop_loss:
        session.status = "stopped_loss"
        return
    if session.races_played < session.config.max_races:
        return
    if allow_recovery_overrun:
        has_recovery = any(
            (c.level > 0 and not c.busted)
            for c in session.recovery_chains.values()
        )
        if has_recovery:
            return
    session.status = "stopped_max"
