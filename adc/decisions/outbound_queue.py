"""Module 1.3.3  Outbound Queue.

Responsibility : hold messages awaiting acknowledgement, in order.
Secret         : how the queue is represented and persisted.

Implements FR-COM-03, FR-COM-04, NFR-AUD-04, NFR-AVL-02.

State invariant:
    INV-Q1  a message keeps its original id for its whole life
    INV-Q2  pending messages are delivered in the order they were recorded
"""
from typing import Any, Dict, List, Optional


class _Entry:
    def __init__(self, msg_id: str, kind: str, payload: Dict[str, Any], seq: int):
        self.msg_id = msg_id
        self.kind = kind
        self.payload = payload
        self.seq = seq
        self.acknowledged = False


class OutboundQueue:
    def __init__(self):
        self._entries: List[_Entry] = []
        self._next_seq = 1

    def enqueue(self, msg_id: str, kind: str, payload: Dict[str, Any]) -> int:
        """Record a message for delivery. FR-COM-02."""
        e = _Entry(msg_id, kind, dict(payload), self._next_seq)
        self._entries.append(e)
        self._next_seq += 1
        self._check_invariant()
        return e.seq

    def pending(self):
        """Unacknowledged messages, oldest first. FR-COM-04."""
        return [e for e in self._entries if not e.acknowledged]

    def pending_count(self) -> int:
        return len(self.pending())

    def next_to_send(self) -> Optional[_Entry]:
        p = self.pending()
        return p[0] if p else None

    def acknowledge(self, msg_id: str) -> bool:
        """Mark delivered only on an acknowledgement matching the message id."""
        for e in self._entries:
            if e.msg_id == msg_id and not e.acknowledged:
                e.acknowledged = True
                self._check_invariant()
                return True
        return False

    def describe_pending(self):
        return [(e.seq, e.msg_id, e.kind) for e in self.pending()]

    def _check_invariant(self) -> None:
        seqs = [e.seq for e in self._entries]
        if seqs != sorted(seqs):
            raise AssertionError("INV-Q2 violated: queue is out of order")
