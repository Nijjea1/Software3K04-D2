"""Every cell of every transition table says something.

Week 7 slide 33: a blank cell is a transition nobody decided.
"""
import unittest

from adc.behaviour.drawer_state import (DrawerEvent, DrawerServiceState,
                                        DrawerStateTable)
from adc.behaviour.mode_manager import Mode, ModeEvent, ModeManager


class TransitionTablesAreTotal(unittest.TestCase):

    # This test reads the table itself rather than running the machine. It is
    # the cheapest way to prove no cell was forgotten.
    def test_mode_table_has_every_state_event_cell(self):
        table = ModeManager._T
        self.assertEqual(set(table.keys()), set(Mode))
        for mode in Mode:
            self.assertEqual(set(table[mode].keys()), set(ModeEvent),
                             "mode %s is missing an event column" % mode)

    def test_drawer_table_has_every_state_event_cell(self):
        table = DrawerStateTable._T
        self.assertEqual(set(table.keys()), set(DrawerServiceState))
        for state in DrawerServiceState:
            self.assertEqual(set(table[state].keys()), set(DrawerEvent),
                             "state %s is missing an event column" % state)

    def test_critical_fault_from_every_operating_mode_enters_fault(self):
        for start in (Mode.NORMAL, Mode.MAINTENANCE):
            mm = ModeManager()
            mm.handle(ModeEvent.STARTUP_OK)
            if start is Mode.MAINTENANCE:
                mm.handle(ModeEvent.MAINTENANCE_REQUESTED)
            mm.handle(ModeEvent.CRITICAL_FAULT, reason="LOCK_MISMATCH")
            self.assertIs(mm.mode(), Mode.FAULT)

    def test_fault_cannot_be_left_without_a_passing_self_test(self):
        mm = ModeManager()
        mm.handle(ModeEvent.STARTUP_OK)
        mm.handle(ModeEvent.CRITICAL_FAULT, reason="LOCK_MISMATCH")
        changed, note = mm.handle(ModeEvent.RESET_REQUESTED, guards_satisfied=False)
        self.assertFalse(changed)
        self.assertIs(mm.mode(), Mode.FAULT)


if __name__ == "__main__":
    unittest.main()
