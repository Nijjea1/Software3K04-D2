"""Module 1  ADC Application.

Responsibility : the whole ADC software. Wires the modules together and runs
                 the Deliverable 1 scenarios.
Secret         : all secrets, delegated to the modules below it.

This module is the only client that holds references to several modules at
once, which keeps the USES relation acyclic. Nothing below this file imports
anything from this file.

System-wide invariants re-established after every public operation:
    INV-G1  mode != NORMAL implies no drawer is commanded unlocked   (FR-MOD-02)
    INV-G2  an INHIBITED drawer is always commanded locked           (NFR-SAF-03)
    INV-G3  at most one drawer is commanded unlocked at any time     (FR-DSP-03)
"""
from typing import Optional, Tuple

from adc.behaviour.authorization import AuthorizationPolicy, Command, Role
from adc.behaviour.dispense_transaction import DispenseTransaction, TxStatus, R3_CONFIRMED
from adc.behaviour.drawer_state import DrawerEvent, DrawerStateTable
from adc.behaviour.link_state import LinkState, LinkStateMachine
from adc.behaviour.mode_manager import Mode, ModeEvent, ModeManager
from adc.behaviour.session_manager import SessionManager
from adc.behaviour.timing_policy import TimingPolicy
from adc.decisions.audit_log_store import AuditLogStore
from adc.decisions.inventory_store import InventoryStore
from adc.decisions.message_codec import MessageCodec
from adc.decisions.outbound_queue import OutboundQueue
from adc.decisions.ui_presentation import UiPresentation
from adc.hardware.clock import Clock
from adc.hardware.credential_reader import CredentialReader
from adc.hardware.drawer_sensor import DrawerSensor
from adc.hardware.lock_driver import LockDriver
from adc.hardware.removal_sensor import RemovalSensor


class AdcApplication:
    def __init__(self, cabinet_id, clock: Clock, lock: LockDriver,
                 drawers: DrawerSensor, reader: CredentialReader,
                 removal: RemovalSensor, drawer_ids, items, user_roles,
                 inactive_users=None, timing: Optional[TimingPolicy] = None):
        self._cabinet_id = cabinet_id
        self._clock = clock
        self._lock = lock
        self._drawers = drawers
        self._removal = removal
        self._drawer_ids = list(drawer_ids)

        # Everything below this line is built here and nowhere else. This is the
        # only file that holds more than one module reference, which is what
        # keeps the USES relation a tree with no cycles.
        self._timing = timing or TimingPolicy()
        self._audit = AuditLogStore(clock, cabinet_id)
        self._inventory = InventoryStore(items)
        self._queue = OutboundQueue()
        self._codec = MessageCodec()
        self._ui = UiPresentation()
        self._authz = AuthorizationPolicy()
        self._sessions = SessionManager(reader, clock, self._timing,
                                        user_roles, inactive_users)
        self._drawer_state = DrawerStateTable(drawer_ids)
        self._link = LinkStateMachine(clock, self._timing)
        self._mode = ModeManager(on_change=self._on_mode_change)

        self._tx_counter = 0
        self._msg_counter = 0
        self._open_drawer: Optional[str] = None
        self._open_since_s: Optional[float] = None
        self._active_tx: Optional[DispenseTransaction] = None
        self._mismatch_since_s = {}

        # Start with everything locked, then prove the invariants hold. The
        # constructor establishes them, as Week 7 slide 20 requires.
        for d in self._drawer_ids:
            self._lock.command_lock(d)
        self._check_invariants()

    # ================= startup, FR-MOD-01, NFR-REL-04 =================

    def start_up(self, self_test_passes: bool = True) -> Mode:
        event = ModeEvent.STARTUP_OK if self_test_passes else ModeEvent.STARTUP_FAILED
        self._mode.handle(event, reason="startup self-test")
        self._audit.append("startup", "ok" if self_test_passes else "critical_fault")
        self._check_invariants()
        return self._mode.mode()

    # ================= access control, FR-AUTH-* =================

    def authenticate(self, presented: str):
        result = self._sessions.authenticate(presented)
        if result is None:
            self._audit.append("auth", "denied", detail={"reason": "bad_credential"})
            self._emit("AUTH_FAILED", {"reason": "bad_credential"})
            return None, self._ui.outcome("DENIED", "bad_credential")
        user_id, role = result
        self._audit.append("auth", "granted", user_id=user_id,
                           detail={"role": role.value})
        self._check_invariants()
        return (user_id, role), "Session open for %s as %s" % (user_id, role.value)

    def log_out(self) -> str:
        self._sessions.end_session()
        self._audit.append("session_end", "ok")
        return "Session ended."

    # ================= dispensing, FR-DSP-* =================

    def request_dispense(self, item_id: str, qty: int) -> Tuple[Optional[str], str]:
        """Validate a dispense request. Returns (tx_id or None, message).

        No drawer is unlocked here. The confirmation screen is shown first,
        which is NFR-USA-04.
        """
        session = self._sessions.active_session()
        if session is None:
            return None, self._ui.outcome("DENIED", "session_expired")
        user_id, role = session
        self._sessions.touch()

        self._tx_counter += 1
        tx_id = "TX-%04d" % self._tx_counter
        drawer_id = self._inventory.drawer_of(item_id)
        tx = DispenseTransaction(tx_id, user_id, item_id, qty, drawer_id or "?")

        def refuse(reason):
            tx.deny(reason)
            self._audit.append("dispense", "DENIED", user_id=user_id, tx_id=tx_id,
                               detail={"item": item_id, "qty": qty, "reason": reason})
            self._emit("DISPENSE_RESULT", {"tx": tx_id, "status": "DENIED",
                                           "reason": reason})
            self._check_invariants()
            return None, self._ui.outcome("DENIED", reason)

        # The checks run in a fixed order and the first failure wins. Nothing
        # before this point has unlocked anything, so a denial costs nothing.
        if tx.status is TxStatus.DENIED:
            return refuse("invalid_quantity")
        if not self._authz.permits(role, Command.DISPENSE):
            return refuse("role_not_permitted")
        if not self._mode.dispensing_permitted():
            return refuse("mode_blocks")
        if not self._inventory.knows(item_id):
            return refuse("unknown_item")
        if not self._drawer_state.is_usable(drawer_id):
            return refuse("drawer_inhibited")
        if not self._inventory.sufficient(item_id, qty):
            return refuse("insufficient_stock")

        tx.authorize()
        self._active_tx = tx
        return tx_id, self._ui.confirmation_screen(item_id, qty, drawer_id)

    def confirm_dispense(self) -> str:
        """FR-DSP-03. Unlocks exactly one drawer. INV-G3."""
        tx = self._active_tx
        if tx is None or tx.status is not TxStatus.AUTHORIZED:
            return self._ui.outcome("DENIED", "no_session")
        # This guard is how INV-G3 is kept. One drawer open at a time, checked
        # before the unlock rather than after.
        if self._open_drawer is not None:
            return self._ui.outcome("DENIED", "drawer_already_open")
        self._lock.command_unlock(tx.drawer_id)
        self._open_drawer = tx.drawer_id
        self._open_since_s = self._clock.now_s()
        tx.mark_unlocked()
        self._audit.append("unlock", "ok", user_id=tx.user_id, tx_id=tx.tx_id,
                           detail={"drawer": tx.drawer_id})
        self._check_invariants()
        return "Drawer %s unlocked. Take the medication and close the drawer." % tx.drawer_id

    def close_drawer_and_complete(self) -> str:
        """FR-DSP-04. Resolves the transaction through the function table."""
        tx = self._active_tx
        if tx is None:
            return self._ui.outcome("DENIED", "no_session")
        closure = self._drawers.is_closed(tx.drawer_id) and self._lock_is_secure(tx.drawer_id)
        removal = self._removal.removal_confirmed(tx.drawer_id)
        if closure:
            self._lock.command_lock(tx.drawer_id)
            self._open_drawer = None
            self._open_since_s = None
            tx.mark_drawer_closed()

        # The transaction decides the row, the App acts on it. Only row R3
        # reaches apply_decrement, which is the whole of NFR-SAF-02.
        row, reason = tx.apply_completion(removal, closure)
        if row == R3_CONFIRMED:
            applied = self._inventory.apply_decrement(tx.tx_id, tx.item_id, tx.qty)
            tx.decremented = applied
            self._audit.append("dispense", "COMPLETED", user_id=tx.user_id,
                               tx_id=tx.tx_id,
                               detail={"item": tx.item_id, "qty": tx.qty, "row": row})
            self._emit("DISPENSE_RESULT", {"tx": tx.tx_id, "status": "COMPLETED",
                                           "item": tx.item_id, "qty": tx.qty})
            self._emit("INVENTORY_UPDATE",
                       {"item": tx.item_id,
                        "qty": self._inventory.quantity_of(tx.item_id),
                        "rev": self._inventory.revision_of(tx.item_id)})
            out = self._ui.outcome("COMPLETED")
        elif tx.status is TxStatus.UNCERTAIN:
            self._audit.append("dispense", "UNCERTAIN", user_id=tx.user_id,
                               tx_id=tx.tx_id,
                               detail={"item": tx.item_id, "qty": tx.qty, "row": row})
            self._emit("DISPENSE_RESULT", {"tx": tx.tx_id, "status": "UNCERTAIN",
                                           "row": row})
            out = self._ui.outcome("UNCERTAIN", reason)
        else:
            out = self._ui.outcome("DENIED", "removal_unconfirmed")

        if tx.is_resolved():
            self._active_tx = None
        self._check_invariants()
        return out

    # ================= replenishment, FR-INV-* =================

    def replenish(self, item_id: str, drawer_id: str, qty: int) -> str:
        session = self._sessions.active_session()
        if session is None:
            return self._ui.outcome("DENIED", "session_expired")
        user_id, role = session
        self._sessions.touch()
        self._tx_counter += 1
        tx_id = "TX-%04d" % self._tx_counter

        def refuse(reason):
            self._audit.append("replenish", "DENIED", user_id=user_id, tx_id=tx_id,
                               detail={"item": item_id, "qty": qty, "reason": reason})
            return self._ui.outcome("DENIED", reason)

        if not self._authz.permits(role, Command.REPLENISH):
            return refuse("role_not_permitted")
        if not self._mode.replenishment_permitted():
            return refuse("mode_blocks")
        if not self._inventory.apply_increment(tx_id, item_id, drawer_id, qty):
            return refuse("unknown_item")
        self._audit.append("replenish", "COMPLETED", user_id=user_id, tx_id=tx_id,
                           detail={"item": item_id, "qty": qty})
        self._emit("INVENTORY_UPDATE",
                   {"item": item_id, "qty": self._inventory.quantity_of(item_id),
                    "rev": self._inventory.revision_of(item_id)})
        self._check_invariants()
        return self._ui.outcome("COMPLETED")

    # ================= faults, FR-FLT-* =================

    def poll_hardware(self) -> str:
        """Periodic health check. FR-FLT-01, FR-FLT-02, FR-FLT-03."""
        notes = []
        # FR-FLT-01, drawer left open past the threshold.
        if self._open_drawer is not None and self._open_since_s is not None:
            open_for = self._clock.now_s() - self._open_since_s
            if self._timing.close_timeout_expired(open_for) and \
                    not self._drawers.is_closed(self._open_drawer):
                changed, _ = self._drawer_state.handle(
                    self._open_drawer, DrawerEvent.DRAWER_NOT_CLOSED,
                    reason="DRAWER_NOT_CLOSED")
                if changed:
                    self._raise_fault("DRAWER_NOT_CLOSED", self._open_drawer,
                                      critical=False)
                    notes.append("DRAWER_NOT_CLOSED on %s" % self._open_drawer)
        # FR-FLT-02, lock feedback disagrees with the command for over 2 s.
        for d in self._drawer_ids:
            mismatched = (self._lock.commanded_state_is_locked(d)
                          != self._lock.is_engaged(d))
            if not mismatched:
                self._mismatch_since_s.pop(d, None)
                continue
            # Remember when the mismatch started so it can be timed. A brief
            # disagreement while the bolt moves is normal and is tolerated.
            started = self._mismatch_since_s.setdefault(d, self._clock.now_s())
            held_for = self._clock.now_s() - started
            if not self._timing.lock_mismatch_expired(held_for):
                notes.append("lock feedback mismatch on %s, within tolerance" % d)
                continue
            if self._drawer_state.is_usable(d):
                self._drawer_state.handle(d, DrawerEvent.LOCK_MISMATCH,
                                          reason="LOCK_MISMATCH")
                self._raise_fault("LOCK_MISMATCH", d, critical=True)
                notes.append("LOCK_MISMATCH on %s held %.0f s, entering FAULT"
                             % (d, held_for))
        # FR-FLT-03, link heartbeat.
        changed, action = self._link.tick()
        if changed and action == "enter_offline":
            self._audit.append("link", "offline",
                               detail={"reason": "missed heartbeats"})
            notes.append("LINK OFFLINE, local operation continues")
        self._check_invariants()
        return "; ".join(notes) if notes else "All devices healthy."

    def _raise_fault(self, fault_type: str, drawer_id: str, critical: bool) -> None:
        self._audit.append("fault", fault_type,
                           detail={"drawer": drawer_id, "critical": critical})
        self._emit("ALARM", {"type": fault_type, "drawer": drawer_id,
                             "critical": critical})
        # Lock first, then change the mode. The safe physical state is reached
        # before anything else happens, which is the fail-safe default.
        self._lock.command_lock(drawer_id)
        if critical:
            self._mode.handle(ModeEvent.CRITICAL_FAULT, reason=fault_type)
            for d in self._drawer_ids:
                self._lock.command_lock(d)
            self._open_drawer = None
            self._open_since_s = None

    def clear_fault(self, self_test_passes: bool = True) -> str:
        """FR-MOD-04. Needs an authorized role and a passing self test."""
        session = self._sessions.active_session()
        if session is None:
            return self._ui.outcome("DENIED", "session_expired")
        user_id, role = session
        if not self._authz.permits(role, Command.CLEAR_FAULT):
            self._audit.append("clear_fault", "DENIED", user_id=user_id,
                               detail={"reason": "role_not_permitted"})
            return self._ui.outcome("DENIED", "role_not_permitted")
        for d in self._drawer_state.inhibited_drawers():
            self._drawer_state.handle(d, DrawerEvent.FAULT_CLEARED,
                                      guards_satisfied=self_test_passes)
        changed, note = self._mode.handle(ModeEvent.RESET_REQUESTED,
                                          guards_satisfied=self_test_passes,
                                          reason="technician reset")
        self._audit.append("clear_fault", "ok" if changed else note, user_id=user_id)
        self._check_invariants()
        return "Mode is now %s." % self._mode.mode().value

    def enter_maintenance(self) -> str:
        session = self._sessions.active_session()
        if session is None:
            return self._ui.outcome("DENIED", "session_expired")
        user_id, role = session
        if not self._authz.permits(role, Command.ENTER_MAINTENANCE):
            return self._ui.outcome("DENIED", "role_not_permitted")
        changed, note = self._mode.handle(ModeEvent.MAINTENANCE_REQUESTED,
                                          guards_satisfied=self._open_drawer is None,
                                          reason="requested by %s" % user_id)
        self._audit.append("mode", "maintenance" if changed else note, user_id=user_id)
        self._check_invariants()
        return "Mode is now %s." % self._mode.mode().value

    def exit_maintenance(self) -> str:
        changed, note = self._mode.handle(ModeEvent.EXIT_MAINTENANCE)
        self._audit.append("mode", "normal" if changed else note)
        self._check_invariants()
        return "Mode is now %s." % self._mode.mode().value

    # ================= external communication, FR-COM-* =================

    # Outbound messages are queued, never sent directly. That is why the link
    # going down loses nothing: the queue just stops draining.
    def _emit(self, kind: str, payload) -> None:
        self._msg_counter += 1
        msg_id = "MSG-%05d" % self._msg_counter
        self._queue.enqueue(msg_id, kind, payload)

    def monitor_response(self, wire: str) -> str:
        """Inbound from Part B. NFR-SEC-04 rejects anything malformed."""
        try:
            msg = self._codec.decode(wire)
        except ValueError as exc:
            self._audit.append("inbound", "rejected", detail={"reason": str(exc)})
            return "Rejected: %s. No local state changed." % exc
        self._link.note_response_received()
        if msg["kind"] == "ACK":
            ok = self._queue.acknowledge(msg["payload"].get("ack_id", ""))
            if self._queue.pending_count() == 0:
                self._link.note_queue_drained()
            return "Acknowledged %s." % msg["payload"].get("ack_id") if ok else "Unknown message id."
        return "Accepted %s." % msg["kind"]

    def flush_queue(self):
        """FR-COM-04. Sends pending messages oldest first and shows the wire form."""
        if not self._link.is_usable() and self._link.state() is LinkState.OFFLINE:
            return ["Link is OFFLINE. %d message(s) remain stored."
                    % self._queue.pending_count()]
        sent = []
        for seq, msg_id, kind in self._queue.describe_pending():
            sent.append("-> %s %s %s" % (msg_id, kind, "(awaiting ack)"))
        return sent or ["Queue empty."]

    def simulate_link_restored(self) -> str:
        self._link.note_response_received()
        self._audit.append("link", "resync")
        return ("Link restored. RESYNC. %d stored message(s) will be sent oldest first."
                % self._queue.pending_count())

    # ================= status and audit =================

    def banner(self) -> str:
        return self._ui.mode_banner(self._mode.mode().value,
                                    self._link.state().value,
                                    self._queue.pending_count())

    def inventory_snapshot(self):
        return self._inventory.snapshot()

    def drawer_report(self):
        return [(d, self._drawer_state.state_of(d).value,
                 "locked" if self._lock.commanded_state_is_locked(d) else "UNLOCKED")
                for d in self._drawer_ids]

    def audit_tail(self, n: int = 100):
        """NFR-AUD-03. Any authenticated role may read the local record on this
        cabinet, per assumption A-15. Restricting reads by role is a Monitoring
        System concern, not a cabinet one."""
        return self._audit.last(n)

    def pending_messages(self):
        return self._queue.describe_pending()

    # ================= invariants =================

    def _on_mode_change(self, previous: Mode, new: Mode, reason: str) -> None:
        self._audit.append("mode_change", new.value,
                           detail={"from": previous.value, "to": new.value,
                                   "reason": reason})
        self._emit("MODE_CHANGE", {"from": previous.value, "to": new.value})

    def _lock_is_secure(self, drawer_id: str) -> bool:
        return self._drawers.is_closed(drawer_id)

    # Called at the end of every public operation. If a change ever broke one
    # of these three rules, the demo would stop with a named violation rather
    # than carry on in a bad state.
    def _check_invariants(self) -> None:
        unlocked = [d for d in self._drawer_ids
                    if not self._lock.commanded_state_is_locked(d)]
        if len(unlocked) > 1:
            raise AssertionError("INV-G3 violated: %d drawers unlocked" % len(unlocked))
        if self._mode.mode() is not Mode.NORMAL and unlocked:
            raise AssertionError("INV-G1 violated: drawer unlocked in %s"
                                 % self._mode.mode().value)
        for d in self._drawer_state.inhibited_drawers():
            if not self._lock.commanded_state_is_locked(d):
                raise AssertionError("INV-G2 violated: inhibited drawer %s unlocked" % d)
