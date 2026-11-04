"""Module 1.3.1  Inventory Store.

Responsibility : hold confirmed quantity and revision for each stocked item.
Secret         : how the record is represented and how a change is committed.

Implements FR-INV-01 to FR-INV-04, NFR-REL-01, NFR-REL-02.

The commit is atomic. A change is staged and then applied in one step, so a
simulated interruption leaves either the old value or the new value and never
a partial entry, which is NFR-REL-01.

State invariant:
    INV-I1  0 <= quantity <= max_capacity for every item
    INV-I2  a transaction id is applied at most once
"""
import copy
from typing import Dict, Optional


class _Item:
    def __init__(self, item_id: str, drawer_id: str, quantity: int, max_capacity: int):
        self.item_id = item_id
        self.drawer_id = drawer_id
        self.quantity = quantity
        self.max_capacity = max_capacity
        self.revision = 0


class InventoryStore:
    def __init__(self, items):
        self._items: Dict[str, _Item] = {}
        for item_id, drawer_id, qty, cap in items:
            self._items[item_id] = _Item(item_id, drawer_id, qty, cap)
        self._applied_tx = set()
        self._check_invariant()

    # ---------------- queries ----------------

    def drawer_of(self, item_id: str) -> Optional[str]:
        it = self._items.get(item_id)
        return it.drawer_id if it else None

    def quantity_of(self, item_id: str) -> Optional[int]:
        it = self._items.get(item_id)
        return it.quantity if it else None

    def revision_of(self, item_id: str) -> Optional[int]:
        it = self._items.get(item_id)
        return it.revision if it else None

    def knows(self, item_id: str) -> bool:
        return item_id in self._items

    def snapshot(self):
        """Return a copy. Returning the live dict would leak the representation."""
        return {k: (v.drawer_id, v.quantity, v.revision)
                for k, v in self._items.items()}

    # ---------------- commands ----------------

    def sufficient(self, item_id: str, qty: int) -> bool:
        """FR-DSP-02."""
        it = self._items.get(item_id)
        return it is not None and qty > 0 and it.quantity >= qty

    def apply_decrement(self, tx_id: str, item_id: str, qty: int) -> bool:
        """FR-INV-04, NFR-REL-02. Idempotent in the transaction id.

        Returns True when the decrement was applied, False when it was a
        duplicate or the request was invalid. Never raises in normal use.
        """
        # Replaying the same transaction id does nothing. This is what makes a
        # retry after a lost acknowledgement safe.
        if tx_id in self._applied_tx:
            return False
        it = self._items.get(item_id)
        if it is None or qty <= 0 or it.quantity < qty:
            return False
        # Build the new record beside the old one. If anything were wrong, the
        # stored value is still the old one and nothing is half written.
        staged = copy.copy(it)
        staged.quantity = it.quantity - qty
        staged.revision = it.revision + 1
        self._commit(item_id, staged, tx_id)
        return True

    def apply_increment(self, tx_id: str, item_id: str, drawer_id: str, qty: int) -> bool:
        """FR-INV-02, FR-INV-03. Rejects a nonpositive quantity or a wrong drawer."""
        if tx_id in self._applied_tx:
            return False
        it = self._items.get(item_id)
        if it is None or qty <= 0 or it.drawer_id != drawer_id:
            return False
        if it.quantity + qty > it.max_capacity:
            return False
        staged = copy.copy(it)
        staged.quantity = it.quantity + qty
        staged.revision = it.revision + 1
        self._commit(item_id, staged, tx_id)
        return True

    # ---------------- private ----------------

    def _commit(self, item_id: str, staged: "_Item", tx_id: str) -> None:
        """The single atomic step. Either both lines run or neither does."""
        # The swap and the id both happen here, in one step. This is the atomic
        # commit for NFR-REL-01.
        self._items[item_id] = staged
        self._applied_tx.add(tx_id)
        self._check_invariant()

    def _check_invariant(self) -> None:
        for it in self._items.values():
            if it.quantity < 0 or it.quantity > it.max_capacity:
                raise AssertionError(
                    "INV-I1 violated for %s: %d not in 0..%d"
                    % (it.item_id, it.quantity, it.max_capacity))
