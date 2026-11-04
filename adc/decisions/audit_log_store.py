"""Module 1.3.2  Audit Log Store.

Responsibility : append and retrieve audit records.
Secret         : the record format and where records are stored.

Implements FR-LOG-01 to FR-LOG-03, NFR-AUD-01 to NFR-AUD-03, NFR-SEC-01.

Anticipated change: records move from an in-memory list to a file or a
database. Only this module changes, because clients never see the container.

State invariant:
    INV-A1  records are append-only and sequence numbers increase by one
    INV-A2  no record contains a credential token
"""
from typing import Any, Dict, List, Optional

from adc.hardware.clock import Clock

# Keys that must never appear in a record. NFR-SEC-01.
_FORBIDDEN = ("token", "credential", "password", "secret")


# Owns the audit trail. Records can be added and read, never changed or removed.
class AuditLogStore:
    # Starts an empty log numbered from one, tied to this cabinet.
    def __init__(self, clock: Clock, cabinet_id: str):
        self._clock = clock
        self._cabinet_id = cabinet_id
        self._records: List[Dict[str, Any]] = []
        self._next_seq = 1
        self._check_invariant()

    # Adds one record and returns its number, refusing anything that looks like a credential.
    def append(self, event_type: str, outcome: str,
               user_id: Optional[str] = None, tx_id: Optional[str] = None,
               detail: Optional[Dict[str, Any]] = None) -> int:
        """Append one record and return its sequence number.

        Effects    : the record is durable from the caller's point of view.
        Exceptions : a detail key that looks like a credential raises, so the
                     NFR-SEC-01 violation is caught at the boundary rather
                     than silently written.
        """
        # Screening happens here, at the boundary. A caller that tries to log a
        # token gets an exception instead of a written record.
        detail = dict(detail or {})
        for key in detail:
            if any(f in key.lower() for f in _FORBIDDEN):
                raise AssertionError(
                    "INV-A2 violated: refusing to log key %r" % key)
        record = {
            "seq": self._next_seq,
            "timestamp_s": round(self._clock.now_s(), 3),
            "cabinet_id": self._cabinet_id,
            "event_type": event_type,
            "outcome": outcome,
            "user_id": user_id,
            "tx_id": tx_id,
            "detail": detail,
        }
        # Append only. There is no update and no delete method, so a record
        # cannot be changed after the fact. That is NFR-AUD-01.
        self._records.append(record)
        self._next_seq += 1
        self._check_invariant()
        return record["seq"]

    # Returns copies of the most recent records, oldest of them first.
    def last(self, n: int = 100):
        """NFR-AUD-03. Chronological order, newest last. Returns copies."""
        return [dict(r) for r in self._records[-n:]]

    # Says how many records the log holds.
    def count(self) -> int:
        return len(self._records)

    # Proves the record numbers still run one, two, three with no gaps. Raises if not.
    def _check_invariant(self) -> None:
        for i, r in enumerate(self._records):
            if r["seq"] != i + 1:
                raise AssertionError("INV-A1 violated at index %d" % i)
