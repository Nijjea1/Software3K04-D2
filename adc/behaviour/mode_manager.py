"""Module 1.2.4  Mode Manager.

Responsibility : hold the cabinet operating mode and change it.
Secret         : the mode transition table and which faults count as critical.

Realises Figure 8a from Deliverable 1. Implements FR-MOD-01 to FR-MOD-04,
NFR-SAF-04, NFR-REL-04.

The transition table below IS the model, as Week 7 slide 35 describes. Every
cell says one of three things: a transition, IGNORE, or ILLEGAL. A blank cell
is a transition nobody decided, so there are none.

State invariant:
    INV-M1  mode is always exactly one of Mode

Note: "mode != NORMAL implies no drawer is commanded unlocked" is INV-G1 and
is checked in the application module, which owns the lock driver.
"""
from enum import Enum
from typing import Callable, Dict, Optional, Tuple


class Mode(Enum):
    STARTUP = "STARTUP"
    NORMAL = "NORMAL"
    MAINTENANCE = "MAINTENANCE"
    FAULT = "FAULT"


class ModeEvent(Enum):
    STARTUP_OK = "startupComplete_ok"
    STARTUP_FAILED = "startupComplete_failed"
    MAINTENANCE_REQUESTED = "maintenanceRequested"
    EXIT_MAINTENANCE = "exitMaintenance"
    CRITICAL_FAULT = "criticalFaultDetected"
    RESET_REQUESTED = "resetRequested"


IGNORE = "IGNORE"
ILLEGAL = "ILLEGAL"


class ModeManager:
    """Transition table realisation of Figure 8a."""

    # (next_mode, action_name) | IGNORE | ILLEGAL
    _T: Dict[Mode, Dict[ModeEvent, object]] = {
        Mode.STARTUP: {
            ModeEvent.STARTUP_OK:            (Mode.NORMAL, "enter_normal"),
            ModeEvent.STARTUP_FAILED:       (Mode.FAULT, "enter_fault"),
            ModeEvent.MAINTENANCE_REQUESTED: IGNORE,
            ModeEvent.EXIT_MAINTENANCE:     ILLEGAL,
            ModeEvent.CRITICAL_FAULT:       (Mode.FAULT, "enter_fault"),
            ModeEvent.RESET_REQUESTED:      IGNORE,
        },
        Mode.NORMAL: {
            ModeEvent.STARTUP_OK:           ILLEGAL,
            ModeEvent.STARTUP_FAILED:       ILLEGAL,
            ModeEvent.MAINTENANCE_REQUESTED: (Mode.MAINTENANCE, "enter_maintenance"),
            ModeEvent.EXIT_MAINTENANCE:     ILLEGAL,
            ModeEvent.CRITICAL_FAULT:       (Mode.FAULT, "enter_fault"),
            ModeEvent.RESET_REQUESTED:      IGNORE,
        },
        Mode.MAINTENANCE: {
            ModeEvent.STARTUP_OK:           ILLEGAL,
            ModeEvent.STARTUP_FAILED:       ILLEGAL,
            ModeEvent.MAINTENANCE_REQUESTED: IGNORE,
            ModeEvent.EXIT_MAINTENANCE:     (Mode.NORMAL, "enter_normal"),
            ModeEvent.CRITICAL_FAULT:       (Mode.FAULT, "enter_fault"),
            ModeEvent.RESET_REQUESTED:      IGNORE,
        },
        Mode.FAULT: {
            ModeEvent.STARTUP_OK:           ILLEGAL,
            ModeEvent.STARTUP_FAILED:       ILLEGAL,
            ModeEvent.MAINTENANCE_REQUESTED: (Mode.MAINTENANCE, "enter_maintenance"),
            ModeEvent.EXIT_MAINTENANCE:     ILLEGAL,
            ModeEvent.CRITICAL_FAULT:       IGNORE,
            ModeEvent.RESET_REQUESTED:      (Mode.NORMAL, "enter_normal"),
        },
    }

    def __init__(self, on_change: Optional[Callable[[Mode, Mode, str], None]] = None):
        self._mode = Mode.STARTUP
        self._on_change = on_change
        self._last_fault = None
        self._check_invariant()

    # ---------------- exported operations ----------------

    def mode(self) -> Mode:
        return self._mode

    def dispensing_permitted(self) -> bool:
        """FR-MOD-02. True only in NORMAL."""
        return self._mode is Mode.NORMAL

    def replenishment_permitted(self) -> bool:
        """FR-MOD-02. True only in NORMAL."""
        return self._mode is Mode.NORMAL

    def handle(self, event: ModeEvent, guards_satisfied: bool = True,
               reason: str = "") -> Tuple[bool, str]:
        """Apply one event to the mode machine.

        Returns (changed, note). note is the table verdict, so the caller can
        record it, per FR-LOG-03.
        Exceptions: an ILLEGAL cell never changes the mode. It is recorded and
        refused, which is the fail-safe default from NFR-SAF-01.
        """
        # One lookup, then act on what the cell says. Three possible answers:
        # a transition, IGNORE (expected but nothing to do), or ILLEGAL (should
        # not happen, so refuse it and leave the mode alone).
        cell = self._T[self._mode][event]
        if cell is IGNORE:
            self._check_invariant()
            return False, "ignored"
        if cell is ILLEGAL:
            self._check_invariant()
            return False, "illegal"
        # A guard is the extra condition on a transition, for example the self
        # test passing. A failed guard blocks the transition, it is not an error.
        if not guards_satisfied:
            self._check_invariant()
            return False, "guard_not_satisfied"
        next_mode, action = cell
        previous = self._mode
        self._mode = next_mode
        if event is ModeEvent.CRITICAL_FAULT or event is ModeEvent.STARTUP_FAILED:
            self._last_fault = reason
        # The callback lets the App log and announce the change. This module
        # does not know what an audit log or a message queue is.
        if self._on_change is not None:
            self._on_change(previous, next_mode, reason or event.value)
        self._check_invariant()
        return True, action

    def triggering_fault(self):
        """FR-MOD-03. The fault that caused the most recent entry to FAULT."""
        return self._last_fault

    # ---------------- invariant ----------------

    def _check_invariant(self) -> None:
        if not isinstance(self._mode, Mode):
            raise AssertionError("INV-M1 violated: mode is not a Mode")
