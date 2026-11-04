"""Module 1.2.6  Link State.

Responsibility : decide whether the Monitoring System link is usable.
Secret         : heartbeat counting and when the link is declared down.

Realises Figure 8b from Deliverable 1. Implements FR-FLT-03, NFR-AVL-01,
NFR-AVL-03.

The key design point, carried from assumption A-05: a link in OFFLINE never
forces the cabinet into FAULT. The safety function does not depend on the
link, which is the rule on Week 6 slide 13.
"""
from enum import Enum
from typing import Tuple

from adc.behaviour.timing_policy import TimingPolicy
from adc.hardware.clock import Clock


class LinkState(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    RESYNC = "RESYNC"


class LinkStateMachine:
    def __init__(self, clock: Clock, timing: TimingPolicy):
        self._clock = clock
        self._timing = timing
        self._state = LinkState.ONLINE
        self._last_rx_s = clock.now_s()
        self._resync_started_s = None

    def state(self) -> LinkState:
        return self._state

    def is_usable(self) -> bool:
        return self._state is LinkState.ONLINE

    def note_response_received(self) -> Tuple[bool, str]:
        """A valid response arrived from the Monitoring System."""
        # Coming back from OFFLINE goes to RESYNC, not straight to ONLINE. The
        # stored messages have to be cleared out first.
        self._last_rx_s = self._clock.now_s()
        if self._state is LinkState.OFFLINE:
            self._state = LinkState.RESYNC
            self._resync_started_s = self._clock.now_s()
            return True, "enter_resync"
        return False, "ignored"

    def note_queue_drained(self) -> Tuple[bool, str]:
        """All stored messages have been acknowledged."""
        if self._state is LinkState.RESYNC:
            self._state = LinkState.ONLINE
            self._resync_started_s = None
            return True, "enter_online"
        return False, "ignored"

    def tick(self) -> Tuple[bool, str]:
        """Evaluate the heartbeat timeout. FR-FLT-03.

        Effects: declares the link down after the configured number of missed
        heartbeat periods. Never changes the cabinet mode.
        """
        # Only this method can declare the link down, and it never touches the
        # cabinet mode. That separation is assumption A-05: losing the link is
        # not a safety fault.
        silent_for = self._clock.now_s() - self._last_rx_s
        if self._timing.link_declared_down(silent_for) and self._state is not LinkState.OFFLINE:
            self._state = LinkState.OFFLINE
            self._resync_started_s = None
            return True, "enter_offline"
        return False, "ignored"

    def resync_overdue(self) -> bool:
        """NFR-AVL-03. True when replay should already have started."""
        if self._state is not LinkState.RESYNC or self._resync_started_s is None:
            return False
        return self._timing.resync_start_overdue(
            self._clock.now_s() - self._resync_started_s)
