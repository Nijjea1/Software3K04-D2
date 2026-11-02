"""Module 1.2.3  Dispense Transaction.

Responsibility : run one dispense request through its lifecycle.
Secret         : the transaction state machine and the outcome rules.

Realises Figure 9 from Deliverable 1. Implements FR-DSP-01 to FR-DSP-04,
NFR-SAF-01, NFR-SAF-02, NFR-REL-02.

The outcome is decided by the function table in classify_completion below.
Each row has an identifier, R1 to R6, and each row has a unit test named
after it, which is the practice on Week 7 slide 41.

State invariant:
    INV-T1  status COMPLETED implies removal and closure were both confirmed
    INV-T2  status other than COMPLETED implies inventory was not decremented
    INV-T3  at most one drawer is unlocked by this module at any time
"""
from enum import Enum
from typing import Optional, Tuple


class TxStatus(Enum):
    REQUESTED = "REQUESTED"
    AUTHORIZED = "AUTHORIZED"
    UNLOCKED = "UNLOCKED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    UNCERTAIN = "UNCERTAIN"
    DENIED = "DENIED"


# ---- function table for completing a dispense, FR-DSP-04 ----
# Every input condition, disjoint and complete. Blank is not an answer.
R1_WRONG_STATE = "R1_wrong_state"
R2_DUPLICATE = "R2_duplicate"
R3_CONFIRMED = "R3_removal_and_closure_confirmed"
R4_NO_CLOSURE = "R4_closure_not_confirmed"
R5_NO_REMOVAL = "R5_removal_not_confirmed"
R6_NEITHER = "R6_neither_confirmed"


def classify_completion(status: TxStatus, already_resolved: bool,
                        removal_confirmed: bool, closure_confirmed: bool) -> str:
    """Return the row identifier for this input combination.

    The rows are disjoint and together cover every case, so the default arm
    in apply_completion is unreachable unless this table is wrong.
    """
    if already_resolved:
        return R2_DUPLICATE
    if status is not TxStatus.PENDING and status is not TxStatus.UNLOCKED:
        return R1_WRONG_STATE
    if removal_confirmed and closure_confirmed:
        return R3_CONFIRMED
    if removal_confirmed and not closure_confirmed:
        return R4_NO_CLOSURE
    if not removal_confirmed and closure_confirmed:
        return R5_NO_REMOVAL
    return R6_NEITHER


class DispenseTransaction:
    """One dispense. Created by the App for each request."""

    def __init__(self, tx_id: str, user_id: str, item_id: str, qty: int,
                 drawer_id: str):
        if qty <= 0:
            # FR-DSP-01 requires a positive integer quantity.
            self.status = TxStatus.DENIED
            self.denial_reason = "invalid_quantity"
        else:
            self.status = TxStatus.REQUESTED
            self.denial_reason = None
        self.tx_id = tx_id
        self.user_id = user_id
        self.item_id = item_id
        self.qty = qty
        self.drawer_id = drawer_id
        self.decremented = False
        self._resolved = False
        self._check_invariant()

    # ---------------- exported operations ----------------

    def deny(self, reason: str) -> None:
        """FR-DSP-04. No unlock is ever issued on this path, NFR-SAF-01."""
        self.status = TxStatus.DENIED
        self.denial_reason = reason
        self._resolved = True
        self._check_invariant()

    def authorize(self) -> None:
        if self.status is TxStatus.REQUESTED:
            self.status = TxStatus.AUTHORIZED
        self._check_invariant()

    def mark_unlocked(self) -> None:
        if self.status is TxStatus.AUTHORIZED:
            self.status = TxStatus.UNLOCKED
        self._check_invariant()

    def mark_drawer_closed(self) -> None:
        if self.status is TxStatus.UNLOCKED:
            self.status = TxStatus.PENDING
        self._check_invariant()

    def apply_completion(self, removal_confirmed: bool,
                         closure_confirmed: bool) -> Tuple[str, Optional[str]]:
        """Resolve the transaction using the function table.

        Returns (row_id, reason). The caller decrements inventory only when
        row R3 is returned, which is what keeps NFR-SAF-02 true.
        """
        row = classify_completion(self.status, self._resolved,
                                  removal_confirmed, closure_confirmed)
        if row == R1_WRONG_STATE:
            pass                                    # no change, no decrement
        elif row == R2_DUPLICATE:
            pass                                    # NFR-REL-02, idempotent
        elif row == R3_CONFIRMED:
            self.status = TxStatus.COMPLETED
            self._resolved = True
        elif row in (R4_NO_CLOSURE, R5_NO_REMOVAL, R6_NEITHER):
            self.status = TxStatus.UNCERTAIN
            self.denial_reason = "removal_unconfirmed"
            self._resolved = True
        else:
            # Unreachable if the table is complete. Week 7 slide 41.
            raise AssertionError("TBL-COMPLETION-DEFAULT reached, table is incomplete")
        self._check_invariant()
        return row, self.denial_reason

    def is_resolved(self) -> bool:
        return self._resolved

    # ---------------- invariant ----------------

    def _check_invariant(self) -> None:
        if self.status is not TxStatus.COMPLETED and self.decremented:
            raise AssertionError(
                "INV-T2 violated: inventory decremented for a %s transaction"
                % self.status.value)
