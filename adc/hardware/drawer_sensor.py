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


# The drawer position interface. Anything that can tell us whether a drawer is shut fits here.
class DrawerSensor(ABC):
    # Says whether the named drawer is physically shut.
    @abstractmethod
    def is_closed(self, drawer_id: str) -> bool:
        """Return the debounced position. True means closed."""


# The fake drawer switch. Remembers open or closed for each drawer.
class SimulatedDrawerSensor(DrawerSensor):
    # Starts every drawer in the closed position.
    def __init__(self, drawer_ids):
        self._closed: Dict[str, bool] = {d: True for d in drawer_ids}

    # Returns True when the named drawer is recorded as closed.
    def is_closed(self, drawer_id: str) -> bool:
        return self._closed[drawer_id]

    # ---- simulation control, not part of the exported interface ----
    # These two are how the demo opens and closes a drawer by hand. They are
    # not on DrawerSensor, so the software above cannot fake a sensor reading.

    # Demo helper. Pretends somebody pulled the drawer open.
    def set_open(self, drawer_id: str) -> None:
        self._closed[drawer_id] = False

    # Demo helper. Pretends somebody pushed the drawer shut.
    def set_closed(self, drawer_id: str) -> None:
        self._closed[drawer_id] = True
