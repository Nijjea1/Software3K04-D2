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


class LockDriver(ABC):
    """Exported interface.

    command_lock / command_unlock are requests. They do not guarantee the
    physical lock moved. is_engaged reports what the feedback contact says,
    which is how FR-FLT-02 can detect a mismatch between the two.
    """

    @abstractmethod
    def command_lock(self, drawer_id: str) -> None:
        """Effect: requests that drawer_id becomes locked."""

    @abstractmethod
    def command_unlock(self, drawer_id: str) -> None:
        """Effect: requests that drawer_id becomes unlocked."""

    @abstractmethod
    def commanded_state_is_locked(self, drawer_id: str) -> bool:
        """Return the last command issued for drawer_id. True means locked."""

    @abstractmethod
    def is_engaged(self, drawer_id: str) -> bool:
        """Return what the feedback contact reports. True means physically locked."""


class SimulatedLockDriver(LockDriver):
    """Simulated implementation.

    inject_feedback_fault lets the demonstration create a LOCK_MISMATCH
    condition without damaging hardware, which is what Week 6 slide 14 asks
    for. It is deliberately not part of the LockDriver interface, so no
    behaviour module can reach it.
    """

    def __init__(self, drawer_ids):
        self._commanded: Dict[str, bool] = {d: True for d in drawer_ids}
        self._actual: Dict[str, bool] = {d: True for d in drawer_ids}
        self._stuck: Dict[str, bool] = {d: False for d in drawer_ids}

    def command_lock(self, drawer_id: str) -> None:
        self._commanded[drawer_id] = True
        if not self._stuck[drawer_id]:
            self._actual[drawer_id] = True

    def command_unlock(self, drawer_id: str) -> None:
        self._commanded[drawer_id] = False
        if not self._stuck[drawer_id]:
            self._actual[drawer_id] = False

    def commanded_state_is_locked(self, drawer_id: str) -> bool:
        return self._commanded[drawer_id]

    def is_engaged(self, drawer_id: str) -> bool:
        return self._actual[drawer_id]

    # ---- simulation control, not part of the exported interface ----
    def inject_feedback_fault(self, drawer_id: str) -> None:
        """The lock stops responding and its feedback disagrees with the command.

        This is the condition FR-FLT-02 detects: feedback that does not match
        the commanded state. The drawer reports not engaged while the software
        believes it commanded locked.
        """
        self._stuck[drawer_id] = True
        self._actual[drawer_id] = not self._commanded[drawer_id]

    def clear_feedback_fault(self, drawer_id: str) -> None:
        self._stuck[drawer_id] = False
        self._actual[drawer_id] = self._commanded[drawer_id]
