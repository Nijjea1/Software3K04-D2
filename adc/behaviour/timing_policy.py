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


# Holds every timeout in the system. Nobody else is allowed to know a threshold.
class TimingPolicy:
    # Stores all six timing values. Changing a threshold is a change to this one place.
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

    # Says whether a session has been idle long enough to be closed.
    # Predicates, not constants. FR-AUTH-04.
    def session_has_expired(self, idle_for_s: float) -> bool:
        return idle_for_s >= self._session_idle_s

    # Says whether a drawer has been left open too long.
    # FR-FLT-01.
    def close_timeout_expired(self, open_for_s: float) -> bool:
        return open_for_s >= self._drawer_close_s

    # Says whether a lock has disagreed with its command for long enough to count as a fault.
    # FR-FLT-02.
    def lock_mismatch_expired(self, mismatched_for_s: float) -> bool:
        return mismatched_for_s >= self._lock_mismatch_s

    # Says whether enough heartbeats have been missed to call the link down.
    # FR-FLT-03.
    def link_declared_down(self, silent_for_s: float) -> bool:
        return silent_for_s >= self._heartbeat_period_s * self._missed_allowed

    # Says whether replay of stored messages should have started by now.
    # NFR-AVL-03.
    def resync_start_overdue(self, since_restore_s: float) -> bool:
        return since_restore_s >= self._resync_start_s

    # Returns how often the link should be checked, which a caller genuinely needs to know.
    # The one number that does leak out, and only because a caller has to know
    # how often to run the tick. Everything else stays behind a question.
    def heartbeat_period_s(self) -> float:
        """Exported because the scheduler must know how often to tick."""
        return self._heartbeat_period_s
