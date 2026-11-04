"""Module 1.2.1  Session Manager.

Responsibility : hold the active session and expire it.
Secret         : how a session and its idle timer are represented.

Implements FR-AUTH-01, FR-AUTH-02, FR-AUTH-04, NFR-SEC-02, NFR-SEC-03.

State invariant (established by the constructor, re-established by every
public method, as Week 7 slide 20 requires):
    INV-S1  at most one session is active
    INV-S2  an active session always names exactly one user and one role
"""
from typing import Optional

from adc.behaviour.authorization import Role
from adc.behaviour.timing_policy import TimingPolicy
from adc.hardware.clock import Clock
from adc.hardware.credential_reader import CredentialReader


class _Session:
    def __init__(self, user_id: str, role: Role, started_s: float):
        self.user_id = user_id
        self.role = role
        self.last_activity_s = started_s


class SessionManager:
    def __init__(self, reader: CredentialReader, clock: Clock,
                 timing: TimingPolicy, user_roles, inactive_users=None):
        self._reader = reader
        self._clock = clock
        self._timing = timing
        self._roles = dict(user_roles)
        self._inactive = set(inactive_users or ())
        self._session: Optional[_Session] = None
        self._check_invariant()

    # ---------------- exported operations ----------------

    def authenticate(self, presented: str):
        """Open a protected session.

        Returns (user_id, role) on success, or None on failure.
        Effects    : replaces any existing session. The caller records the
                     outcome, per FR-LOG-01.
        Exceptions : an inactive account always fails, per NFR-SEC-03.
        """
        # The reader turns the card into a user id. This module never sees the
        # token itself, which is what makes NFR-SEC-01 possible to enforce.
        user_id = self._reader.read_user_id(presented)
        if user_id is None or user_id in self._inactive:
            self._check_invariant()
            return None
        role = self._roles.get(user_id)
        if role is None:
            self._check_invariant()
            return None
        # Overwriting the single slot is how INV-S1 stays true. There is no
        # list of sessions, so two cannot be active at once.
        self._session = _Session(user_id, role, self._clock.now_s())
        self._check_invariant()
        return user_id, role

    def active_session(self):
        """Return (user_id, role) if a session is active and not expired, else None.

        Effects: expiring a session here is what makes FR-AUTH-04 observable
        without a background thread.
        """
        if self._session is None:
            return None
        # The timeout is checked when somebody asks, not by a timer thread.
        # Lazy expiry keeps the module single-threaded and easy to test.
        idle = self._clock.now_s() - self._session.last_activity_s
        if self._timing.session_has_expired(idle):
            self._session = None
            self._check_invariant()
            return None
        return self._session.user_id, self._session.role

    def touch(self) -> None:
        """Record user activity, resetting the idle timer."""
        if self._session is not None:
            self._session.last_activity_s = self._clock.now_s()
        self._check_invariant()

    def end_session(self) -> None:
        self._session = None
        self._check_invariant()

    # ---------------- invariant ----------------

    def _check_invariant(self) -> None:
        s = self._session
        if s is not None and (s.user_id is None or s.role is None):
            raise AssertionError("INV-S2 violated: session without user or role")
