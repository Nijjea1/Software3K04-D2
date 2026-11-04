"""Module 1.2.5  Drawer State.

Responsibility : hold the per-drawer service state.
Secret         : the inhibit and release rules for one drawer.

Realises Figure 8c from Deliverable 1. Implements FR-FLT-04, NFR-SAF-03.

State invariant:
    INV-D1  a drawer in INHIBITED always has a recorded inhibit reason

Note: "an INHIBITED drawer is always commanded locked" is INV-G2 and is
checked in the application module, because this module deliberately cannot
see the lock driver.
"""
from enum import Enum
from typing import Dict, Tuple

IGNORE = "IGNORE"
ILLEGAL = "ILLEGAL"


# The two service states a single drawer can be in.
class DrawerServiceState(Enum):
    IN_SERVICE = "IN_SERVICE"
    INHIBITED = "INHIBITED"


# The four things that can happen to one drawer.
class DrawerEvent(Enum):
    DRAWER_NOT_CLOSED = "drawerNotClosed"
    LOCK_MISMATCH = "lockMismatch"
    FAULT_CLEARED = "faultCleared"
    DISPENSE_REQUESTED = "dispenseRequested"


# Tracks whether each drawer is in service, and why it was taken out of service.
class DrawerStateTable:
    """One instance holds the state of every drawer."""

    # 2 states x 4 events = 8 cells, and all 8 are filled in. A drawer only
    # leaves INHIBITED on faultCleared, so a fault cannot clear itself.
    _T: Dict[DrawerServiceState, Dict[DrawerEvent, object]] = {
        DrawerServiceState.IN_SERVICE: {
            DrawerEvent.DRAWER_NOT_CLOSED: (DrawerServiceState.INHIBITED, "inhibit"),
            DrawerEvent.LOCK_MISMATCH:     (DrawerServiceState.INHIBITED, "inhibit"),
            DrawerEvent.FAULT_CLEARED:     IGNORE,
            DrawerEvent.DISPENSE_REQUESTED: IGNORE,
        },
        DrawerServiceState.INHIBITED: {
            DrawerEvent.DRAWER_NOT_CLOSED: IGNORE,
            DrawerEvent.LOCK_MISMATCH:     IGNORE,
            DrawerEvent.FAULT_CLEARED:     (DrawerServiceState.IN_SERVICE, "release"),
            DrawerEvent.DISPENSE_REQUESTED: IGNORE,
        },
    }

    # Puts every drawer in service with no inhibit reason recorded.
    def __init__(self, drawer_ids):
        self._state: Dict[str, DrawerServiceState] = {
            d: DrawerServiceState.IN_SERVICE for d in drawer_ids
        }
        self._reason: Dict[str, str] = {}
        self._check_invariant()

    # Returns the service state of one drawer.
    def state_of(self, drawer_id: str) -> DrawerServiceState:
        return self._state[drawer_id]

    # Says whether this drawer can be dispensed from, which a bad drawer blocks.
    def is_usable(self, drawer_id: str) -> bool:
        """FR-FLT-04. A dispense targeting an inhibited drawer is refused."""
        return self._state[drawer_id] is DrawerServiceState.IN_SERVICE

    # Returns why this drawer was taken out of service, or None if it is fine.
    def inhibit_reason(self, drawer_id: str):
        return self._reason.get(drawer_id)

    # Takes one event for one drawer and does what the table cell says.
    def handle(self, drawer_id: str, event: DrawerEvent,
               guards_satisfied: bool = True, reason: str = "") -> Tuple[bool, str]:
        # Look the answer up in the table instead of writing if-statements.
        # The table is the design, this method just reads it.
        cell = self._T[self._state[drawer_id]][event]
        if cell is IGNORE:
            self._check_invariant()
            return False, "ignored"
        if cell is ILLEGAL:
            self._check_invariant()
            return False, "illegal"
        if not guards_satisfied:
            self._check_invariant()
            return False, "guard_not_satisfied"
        # A real transition. Record the reason on the way in and drop it on
        # the way out, which is what keeps INV-D1 true.
        next_state, action = cell
        self._state[drawer_id] = next_state
        if next_state is DrawerServiceState.INHIBITED:
            self._reason[drawer_id] = reason or event.value
        else:
            self._reason.pop(drawer_id, None)
        self._check_invariant()
        return True, action

    # Lists every drawer currently out of service, which the App needs to keep them locked.
    def inhibited_drawers(self):
        return [d for d, s in self._state.items()
                if s is DrawerServiceState.INHIBITED]

    # Proves no drawer is out of service without a recorded reason. Raises if one is.
    def _check_invariant(self) -> None:
        for d, s in self._state.items():
            if s is DrawerServiceState.INHIBITED and d not in self._reason:
                raise AssertionError(
                    "INV-D1 violated: drawer %s is INHIBITED with no reason" % d)
