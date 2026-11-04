"""Module 1.3.3  Outbound Queue.

Responsibility : hold messages awaiting acknowledgement, in order.
Secret         : how the queue is represented and persisted.

Implements FR-COM-03, FR-COM-04, NFR-AUD-04, NFR-AVL-02.

State invariant:
    INV-Q1  a message keeps its original id for its whole life
    INV-Q2  pending messages are delivered in the order they were recorded
"""
from typing import Any, Dict, List, Optional


# One message waiting to go out, with its id, kind, contents and whether it was acknowledged.
class _Entry:
    # Creates one queued message, not yet acknowledged.
    def __init__(self, msg_id: str, kind: str, payload: Dict[str, Any], seq: int):
        self.msg_id = msg_id
        self.kind = kind
        self.payload = payload
        self.seq = seq
        self.acknowledged = False


# Holds messages for the Monitoring System in order until each one is acknowledged.
class OutboundQueue:
    # Starts an empty queue numbered from one.
    def __init__(self):
        self._entries: List[_Entry] = []
        self._next_seq = 1

    # Stores one message for delivery and returns its place in the queue.
    def enqueue(self, msg_id: str, kind: str, payload: Dict[str, Any]) -> int:
        """Record a message for delivery. FR-COM-02."""
        # dict(payload) copies it. Keeping the caller's dict would let them
        # change a message after it was queued.
        e = _Entry(msg_id, kind, dict(payload), self._next_seq)
        self._entries.append(e)
        self._next_seq += 1
        self._check_invariant()
        return e.seq

    # Returns every message still waiting, oldest first.
    def pending(self):
        """Unacknowledged messages, oldest first. FR-COM-04."""
        return [e for e in self._entries if not e.acknowledged]

    # Says how many messages are still waiting, which the status banner shows.
    def pending_count(self) -> int:
        return len(self.pending())

    # Returns the oldest waiting message, which is always the next one out.
    def next_to_send(self) -> Optional[_Entry]:
        p = self.pending()
        return p[0] if p else None

    # Marks one message delivered, but only on an acknowledgement carrying its own id.
    def acknowledge(self, msg_id: str) -> bool:
        """Mark delivered only on an acknowledgement matching the message id."""
        # A message clears only on an acknowledgement carrying its own id, so a
        # stray or repeated ack cannot drop the wrong one.
        for e in self._entries:
            if e.msg_id == msg_id and not e.acknowledged:
                e.acknowledged = True
                self._check_invariant()
                return True
        return False

    # Returns a short readable summary of the waiting messages for the demo.
    def describe_pending(self):
        return [(e.seq, e.msg_id, e.kind) for e in self.pending()]

    # Proves the queue is still in the order things were recorded. Raises if not.
    def _check_invariant(self) -> None:
        seqs = [e.seq for e in self._entries]
        if seqs != sorted(seqs):
            raise AssertionError("INV-Q2 violated: queue is out of order")
