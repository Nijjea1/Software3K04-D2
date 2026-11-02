"""Tests for the state invariants named in the design document."""
import unittest

from adc.app import AdcApplication
from adc.behaviour.authorization import Role
from adc.behaviour.mode_manager import Mode
from adc.decisions.audit_log_store import AuditLogStore
from adc.decisions.inventory_store import InventoryStore
from adc.hardware.clock import SimulatedClock
from adc.hardware.credential_reader import SimulatedCredentialReader
from adc.hardware.drawer_sensor import SimulatedDrawerSensor
from adc.hardware.lock_driver import SimulatedLockDriver
from adc.hardware.removal_sensor import SimulatedRemovalSensor

DRAWERS = ["D1", "D2"]
ITEMS = [("MORPH-10MG", "D1", 12, 40), ("PARA-500MG", "D2", 30, 60)]
TOKENS = {"card-nurse": "u-nurse", "card-tech": "u-tech"}
ROLES = {"u-nurse": Role.NURSE, "u-tech": Role.TECHNICIAN}


def build():
    clock = SimulatedClock()
    lock = SimulatedLockDriver(DRAWERS)
    drawers = SimulatedDrawerSensor(DRAWERS)
    removal = SimulatedRemovalSensor()
    app = AdcApplication("ADC-T", clock, lock, drawers,
                         SimulatedCredentialReader(TOKENS), removal,
                         DRAWERS, ITEMS, ROLES)
    app.start_up()
    return app, clock, lock, drawers, removal


class Invariants(unittest.TestCase):

    def test_INV_G3_only_one_drawer_unlocked(self):
        app, clock, lock, drawers, removal = build()
        app.authenticate("card-nurse")
        app.request_dispense("MORPH-10MG", 1)
        app.confirm_dispense()
        unlocked = [d for d, _, state in app.drawer_report() if state == "UNLOCKED"]
        self.assertEqual(len(unlocked), 1)

    def test_INV_G1_no_unlock_outside_normal(self):
        app, clock, lock, drawers, removal = build()
        app.authenticate("card-tech")
        app.enter_maintenance()
        self.assertEqual(Mode.MAINTENANCE.value, app.banner().split()[1])
        app.authenticate("card-nurse")
        tx, msg = app.request_dispense("MORPH-10MG", 1)
        self.assertIsNone(tx)
        self.assertIn("mode blocks", msg)

    def test_INV_T2_uncertain_never_decrements(self):
        app, clock, lock, drawers, removal = build()
        app.authenticate("card-nurse")
        before = app.inventory_snapshot()["MORPH-10MG"][1]
        app.request_dispense("MORPH-10MG", 2)
        app.confirm_dispense()
        # closure confirmed but removal never confirmed -> row R5 -> UNCERTAIN
        out = app.close_drawer_and_complete()
        self.assertIn("UNCERTAIN", out)
        after = app.inventory_snapshot()["MORPH-10MG"][1]
        self.assertEqual(before, after, "NFR-SAF-02: stock must not move")

    def test_INV_I1_quantity_never_exceeds_capacity(self):
        store = InventoryStore([("X", "D1", 5, 10)])
        self.assertFalse(store.apply_increment("t1", "X", "D1", 99))
        self.assertEqual(store.quantity_of("X"), 5)

    def test_INV_I2_decrement_is_idempotent(self):
        store = InventoryStore([("X", "D1", 5, 10)])
        self.assertTrue(store.apply_decrement("t1", "X", 2))
        self.assertFalse(store.apply_decrement("t1", "X", 2))
        self.assertEqual(store.quantity_of("X"), 3)

    def test_INV_A2_credentials_are_never_logged(self):
        log = AuditLogStore(SimulatedClock(), "ADC-T")
        with self.assertRaises(AssertionError):
            log.append("auth", "granted", detail={"credential_token": "card-nurse"})


if __name__ == "__main__":
    unittest.main()
