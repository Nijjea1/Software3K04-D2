"""Module 1.3.4  Message Codec.

Responsibility : encode and decode messages exchanged with the Monitoring System.
Secret         : the wire format and framing.

Implements FR-COM-01, FR-COM-02. This module is the whole of assumption A-08.

Anticipated change: the Part B sub-team changes the message format or the
transport. Only this module changes, which is the rule on Week 6 slide 12,
"protocol is a secret".
"""
import json
from typing import Any, Dict


class MessageCodec:
    PROTOCOL_VERSION = 1

    def encode(self, msg_id: str, kind: str, payload: Dict[str, Any]) -> str:
        """Return the wire representation. JSON is an implementation choice."""
        # JSON and this field layout are the secret. Part B could switch to a
        # binary format and only this file would change.
        return json.dumps({
            "v": self.PROTOCOL_VERSION,
            "id": msg_id,
            "kind": kind,
            "payload": payload,
        }, sort_keys=True)

    def decode(self, wire: str) -> Dict[str, Any]:
        """Return a validated inbound message.

        Exceptions: a malformed or wrong-version message raises ValueError, so
        FR-COM-04 and NFR-SEC-04 can reject it without changing local state.
        """
        try:
            obj = json.loads(wire)
        except Exception as exc:
            raise ValueError("unparseable message") from exc
        if not isinstance(obj, dict):
            raise ValueError("message is not an object")
        # Version first, then required fields. Every failure raises before any
        # local state is touched, which is what NFR-SEC-04 asks for.
        if obj.get("v") != self.PROTOCOL_VERSION:
            raise ValueError("unsupported protocol version")
        for field in ("id", "kind"):
            if field not in obj:
                raise ValueError("missing field %r" % field)
        return obj
