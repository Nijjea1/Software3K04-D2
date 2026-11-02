"""Module 1.1.2  Drawer Sensor.

Responsibility : report whether a drawer is physically closed.
Secret         : how drawer position is sensed and debounced.

4-variable model mapping
    monitored m_drawerPosition{open, closed} -> input i_drawerClosed: bool

Anticipated change: a different microswitch, or a debounce policy change.
Clients see only a boolean abstraction, never a raw sample or a sample
history, which is the leak Week 7 slide 22 warns about.
"""
from abc import ABC, abstractmethod
from typing import Dict


class DrawerSensor(ABC):
    @abstractmethod
    def is_closed(self, drawer_id: str) -> bool:
        """Return the debounced position. True means closed."""


class SimulatedDrawerSensor(DrawerSensor):
    def __init__(self, drawer_ids):
        self._closed: Dict[str, bool] = {d: True for d in drawer_ids}

    def is_closed(self, drawer_id: str) -> bool:
        return self._closed[drawer_id]

    # ---- simulation control, not part of the exported interface ----
    def set_open(self, drawer_id: str) -> None:
        self._closed[drawer_id] = False

    def set_closed(self, drawer_id: str) -> None:
        self._closed[drawer_id] = True
