"""One test per row of the completeDispense function table.

Named after the rows, as Week 7 slide 41 requires, so a row with no test is
visible at a glance. Run with:  python3 -m unittest discover -s tests
"""
import unittest

from adc.behaviour.dispense_transaction import (
    DispenseTransaction, TxStatus,
    R1_WRONG_STATE, R2_DUPLICATE, R3_CONFIRMED,
    R4_NO_CLOSURE, R5_NO_REMOVAL, R6_NEITHER,
    classify_completion,
)


# Builds a transaction driven all the way to PENDING, ready for the completion table.
# A transaction driven to PENDING, which is the only state the completion
# table treats as a real attempt. Rows R3 to R6 all start from here.
def _pending_tx():
    tx = DispenseTransaction("TX-1", "u-nurse-01", "MORPH-10MG", 2, "D1")
    tx.authorize()
    tx.mark_unlocked()
    tx.mark_drawer_closed()
    return tx


# One test per row of the completeDispense function table, named after the row.
class CompletionTableRows(unittest.TestCase):

    # Row R1. Completing a transaction in the wrong state changes nothing at all.
    def test_R1_wrong_state_makes_no_change(self):
        tx = DispenseTransaction("TX-1", "u", "MORPH-10MG", 2, "D1")  # REQUESTED
        row, _ = tx.apply_completion(True, True)
        self.assertEqual(row, R1_WRONG_STATE)
        self.assertIs(tx.status, TxStatus.REQUESTED)
        self.assertFalse(tx.decremented)

    # Row R2. Completing the same transaction twice does not take stock out twice.
    def test_R2_duplicate_does_not_decrement_again(self):
        tx = _pending_tx()
        first, _ = tx.apply_completion(True, True)
        self.assertEqual(first, R3_CONFIRMED)
        second, _ = tx.apply_completion(True, True)
        self.assertEqual(second, R2_DUPLICATE)
        self.assertIs(tx.status, TxStatus.COMPLETED)

    # Row R3. Both confirmations present, so the dispense completes. The only success row.
    def test_R3_removal_and_closure_confirmed_completes(self):
        tx = _pending_tx()
        row, _ = tx.apply_completion(True, True)
        self.assertEqual(row, R3_CONFIRMED)
        self.assertIs(tx.status, TxStatus.COMPLETED)

    # Row R4. Removal confirmed but the drawer never shut, so the answer is UNCERTAIN.
    def test_R4_closure_not_confirmed_is_uncertain(self):
        tx = _pending_tx()
        row, reason = tx.apply_completion(True, False)
        self.assertEqual(row, R4_NO_CLOSURE)
        self.assertIs(tx.status, TxStatus.UNCERTAIN)
        self.assertEqual(reason, "removal_unconfirmed")

    # Row R5. Drawer shut but removal unconfirmed, so the answer is UNCERTAIN.
    def test_R5_removal_not_confirmed_is_uncertain(self):
        tx = _pending_tx()
        row, _ = tx.apply_completion(False, True)
        self.assertEqual(row, R5_NO_REMOVAL)
        self.assertIs(tx.status, TxStatus.UNCERTAIN)

    # Row R6. Neither confirmation present, so the answer is UNCERTAIN.
    def test_R6_neither_confirmed_is_uncertain(self):
        tx = _pending_tx()
        row, _ = tx.apply_completion(False, False)
        self.assertEqual(row, R6_NEITHER)
        self.assertIs(tx.status, TxStatus.UNCERTAIN)

    # Proves every possible input lands on exactly one row, so the default arm is unreachable.
    def test_table_is_disjoint_and_complete(self):
        """Every input combination maps to exactly one row, so the default
        arm in apply_completion is unreachable."""
        seen = set()
        for status in TxStatus:
            for resolved in (True, False):
                for removal in (True, False):
                    for closure in (True, False):
                        row = classify_completion(status, resolved, removal, closure)
                        self.assertIn(row, {R1_WRONG_STATE, R2_DUPLICATE, R3_CONFIRMED,
                                            R4_NO_CLOSURE, R5_NO_REMOVAL, R6_NEITHER})
                        seen.add(row)
        self.assertEqual(len(seen), 6, "every row should be reachable")


if __name__ == "__main__":
    unittest.main()


# The two rows the command loop cannot reach, because close always shuts the drawer.
class ClosureFalseRows(unittest.TestCase):
    """Rows R4 and R6 are reachable only when the drawer is still open.
    The command loop always closes the drawer, so these are covered here."""

    # Row R4 through the real transaction, not just the table. Status is UNCERTAIN.
    def test_R4_removal_confirmed_but_drawer_still_open(self):
        tx = _pending_tx()
        row, reason = tx.apply_completion(True, False)
        self.assertEqual(row, R4_NO_CLOSURE)
        self.assertIs(tx.status, TxStatus.UNCERTAIN)
        self.assertFalse(tx.decremented)

    # Row R6 through the real transaction. Nothing was confirmed, so nothing moves.
    def test_R6_neither_confirmed_leaves_stock_alone(self):
        tx = _pending_tx()
        row, _ = tx.apply_completion(False, False)
        self.assertEqual(row, R6_NEITHER)
        self.assertFalse(tx.decremented)
