"""Module 1.2.7  Timing Policy.

Responsibility : supply every timeout and threshold used by the system.
Secret         : the timing constants themselves.

This module exists because of assumption A-07. Every number in it is a team
decision that still has to be checked against the lab hardware. Keeping them
here means a revised threshold is a one-file change and no constant is
hard-coded next to the logic that uses it, which is the first drift smell on
Week 7 slide 44.

No constant is exported as a public field. Clients ask questions such as
"has the close timeout expired", not "what is the close timeout", which is
the leak Week 7 slide 22 identifies.
"""


class TimingPolicy:
    # Every number lives in this one constructor. If the lab hardware needs a
    # different threshold, this is the only place that changes.
    def __init__(self,
                 session_idle_s: float = 120.0,
                 drawer_close_s: float = 10.0,
                 lock_mismatch_s: float = 2.0,
                 heartbeat_period_s: float = 5.0,
                 missed_heartbeats_allowed: int = 3,
                 resync_start_s: float = 10.0):
        self._session_idle_s = session_idle_s
        self._drawer_close_s = drawer_close_s
        self._lock_mismatch_s = lock_mismatch_s
        self._heartbeat_period_s = heartbeat_period_s
        self._missed_allowed = missed_heartbeats_allowed
        self._resync_start_s = resync_start_s

    # Predicates, not constants. FR-AUTH-04.
    def session_has_expired(self, idle_for_s: float) -> bool:
        return idle_for_s >= self._session_idle_s

    # FR-FLT-01.
    def close_timeout_expired(self, open_for_s: float) -> bool:
        return open_for_s >= self._drawer_close_s

    # FR-FLT-02.
    def lock_mismatch_expired(self, mismatched_for_s: float) -> bool:
        return mismatched_for_s >= self._lock_mismatch_s

    # FR-FLT-03.
    def link_declared_down(self, silent_for_s: float) -> bool:
        return silent_for_s >= self._heartbeat_period_s * self._missed_allowed

    # NFR-AVL-03.
    def resync_start_overdue(self, since_restore_s: float) -> bool:
        return since_restore_s >= self._resync_start_s

    # The one number that does leak out, and only because a caller has to know
    # how often to run the tick. Everything else stays behind a question.
    def heartbeat_period_s(self) -> float:
        """Exported because the scheduler must know how often to tick."""
        return self._heartbeat_period_s
