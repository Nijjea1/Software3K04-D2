"""Module 1.1.4  Removal Sensor.

Responsibility : report whether removal of an item was confirmed.
Secret         : how confirmed removal is established.

This module is the whole of assumption A-04. The requirement is written about
m_itemRemoved, the medication physically leaving the drawer. The software
only ever has i_removalConfirmed. Those are not the same thing, and the gap
between them is why the UNCERTAIN outcome exists in FR-DSP-04.

Anticipated change: no removal sensor is fitted, so a witnessed human
confirmation is used instead. Only this module changes.
"""
from abc import ABC, abstractmethod


# The removal interface. Anything that can confirm medication actually left the drawer fits here.
class RemovalSensor(ABC):
    # Says whether removal was positively confirmed for this drawer.
    @abstractmethod
    def removal_confirmed(self, drawer_id: str) -> bool:
        """Return True only when removal has been positively confirmed.

        Assumption: a False result means not confirmed, which is not the same
        as confirmed-not-removed. Callers must treat it as UNCERTAIN and must
        not decrement inventory. See NFR-SAF-02.
        """


# The fake removal sensor. Stands in for a real sensor or a witnessed human confirmation.
class SimulatedRemovalSensor(RemovalSensor):
    # Starts with nothing confirmed for any drawer.
    def __init__(self):
        self._confirmed = {}

    # Returns True only if removal was confirmed, and False if we simply do not know.
    # Default False. Not confirmed is the safe answer, and it is deliberately
    # not the same claim as confirmed-not-removed.
    def removal_confirmed(self, drawer_id: str) -> bool:
        return self._confirmed.get(drawer_id, False)

    # ---- simulation control, not part of the exported interface ----

    # Demo helper. Records that removal was or was not confirmed for a drawer.
    def set_confirmed(self, drawer_id: str, value: bool) -> None:
        self._confirmed[drawer_id] = value
