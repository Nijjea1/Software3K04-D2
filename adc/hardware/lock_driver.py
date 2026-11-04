"""Module 1.1.1  Lock Driver.

Responsibility : command a drawer lock and report the lock feedback.
Secret         : how the solenoid is driven and how its feedback is decoded.

4-variable model mapping
    monitored  m_lockState{locked, unlocked}  -> input   i_lockFeedback: bool
    output     o_lockCommand: bool            -> controlled c_drawerLock

Anticipated change: a different lock or feedback contact is fitted. Only this
module changes.
"""
from abc import ABC, abstractmethod
from typing import Dict


# The lock interface. Anything that can drive a drawer lock and report back fits here.
class LockDriver(ABC):
    """Exported interface.

    command_lock / command_unlock are requests. They do not guarantee the
    physical lock moved. is_engaged reports what the feedback contact says,
    which is how FR-FLT-02 can detect a mismatch between the two.
    """

    # Asks the named drawer to lock.
    @abstractmethod
    def command_lock(self, drawer_id: str) -> None:
        """Effect: requests that drawer_id becomes locked."""

    # Asks the named drawer to unlock.
    @abstractmethod
    def command_unlock(self, drawer_id: str) -> None:
        """Effect: requests that drawer_id becomes unlocked."""

    # Says what we last asked for. True means we asked for locked.
    @abstractmethod
    def commanded_state_is_locked(self, drawer_id: str) -> bool:
        """Return the last command issued for drawer_id. True means locked."""

    # Says what the lock actually reports back. True means it really is locked.
    @abstractmethod
    def is_engaged(self, drawer_id: str) -> bool:
        """Return what the feedback contact reports. True means physically locked."""


# The fake lock. Keeps what we asked for and what the lock did as two separate values.
class SimulatedLockDriver(LockDriver):
    """Simulated implementation.

    inject_feedback_fault lets the demonstration create a LOCK_MISMATCH
    condition without damaging hardware, which is what Week 6 slide 14 asks
    for. It is deliberately not part of the LockDriver interface, so no
    behaviour module can reach it.
    """

    # Starts every drawer both commanded locked and actually locked, with no faults.
    def __init__(self, drawer_ids):
        self._commanded: Dict[str, bool] = {d: True for d in drawer_ids}
        self._actual: Dict[str, bool] = {d: True for d in drawer_ids}
        self._stuck: Dict[str, bool] = {d: False for d in drawer_ids}

    # Records the lock request, and moves the real lock too unless it is jammed.
    # Two separate fields. _commanded is what the software asked for, _actual is
    # what the lock really did. A healthy lock keeps them equal, and the gap
    # between them is exactly the fault FR-FLT-02 looks for.
    def command_lock(self, drawer_id: str) -> None:
        self._commanded[drawer_id] = True
        if not self._stuck[drawer_id]:
            self._actual[drawer_id] = True

    # Records the unlock request, and moves the real lock too unless it is jammed.
    def command_unlock(self, drawer_id: str) -> None:
        self._commanded[drawer_id] = False
        if not self._stuck[drawer_id]:
            self._actual[drawer_id] = False

    # Returns the last request we made for this drawer.
    def commanded_state_is_locked(self, drawer_id: str) -> bool:
        return self._commanded[drawer_id]

    # Returns what the lock feedback contact says, which may disagree with the request.
    def is_engaged(self, drawer_id: str) -> bool:
        return self._actual[drawer_id]

    # ---- simulation control, not part of the exported interface ----

    # Demo helper. Jams the lock so its feedback disagrees with the command, which is the FR-FLT-02 fault.
    def inject_feedback_fault(self, drawer_id: str) -> None:
        """The lock stops responding and its feedback disagrees with the command.

        This is the condition FR-FLT-02 detects: feedback that does not match
        the commanded state. The drawer reports not engaged while the software
        believes it commanded locked.
        """
        # Both lines are needed. Setting _stuck alone would stop future moves
        # but leave the two fields agreeing, so no mismatch would be detected.
        self._stuck[drawer_id] = True
        self._actual[drawer_id] = not self._commanded[drawer_id]

    # Demo helper. Unjams the lock and puts the feedback back in step with the command.
    def clear_feedback_fault(self, drawer_id: str) -> None:
        self._stuck[drawer_id] = False
        self._actual[drawer_id] = self._commanded[drawer_id]
