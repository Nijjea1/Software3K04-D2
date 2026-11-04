"""Module 1.2.2  Authorization Policy.

Responsibility : decide whether a role may perform a command.
Secret         : how the role and permission matrix is represented and searched.

Implements FR-AUTH-03 and NFR-SEC-03. Realises the role and permission matrix
from Deliverable 1 section 8.3.

Anticipated change: permissions are revised, or a new role is added. Only the
table below changes. No client writes its own role test.
"""
from enum import Enum
from typing import Dict, Set


class Role(Enum):
    NURSE = "nurse"
    PHARMACIST = "pharmacist"
    TECHNICIAN = "technician"
    SAFETY_REVIEWER = "safety_reviewer"


class Command(Enum):
    DISPENSE = "dispense"
    REPLENISH = "replenish"
    CLEAR_FAULT = "clear_fault"
    ENTER_MAINTENANCE = "enter_maintenance"
    REVIEW_AUDIT = "review_audit"


class AuthorizationPolicy:
    """The matrix is private. Clients only ask the question."""

    # The whole permission matrix from Deliverable 1 section 8.3, in one place.
    # Adding a role is one new line here and no change anywhere else.
    _MATRIX: Dict[Role, Set[Command]] = {
        Role.NURSE: {Command.DISPENSE},
        Role.PHARMACIST: {Command.DISPENSE, Command.REPLENISH,
                          Command.CLEAR_FAULT, Command.ENTER_MAINTENANCE},
        Role.TECHNICIAN: {Command.REPLENISH, Command.CLEAR_FAULT,
                          Command.ENTER_MAINTENANCE},
        Role.SAFETY_REVIEWER: {Command.REVIEW_AUDIT},
    }

    def permits(self, role: Role, command: Command) -> bool:
        """Return True when role may perform command.

        Assumptions : role is an active account. Account status is checked by
                      Session Manager, not here, per NFR-SEC-03.
        Effects     : none. Recording a denial is the caller's job, so that
                      this module stays a pure decision.
        Exceptions  : an unknown role returns False rather than raising, so a
                      configuration error can never open a drawer.
        """
        # .get with an empty-set default is the fail-safe part. An unknown role
        # gets no permissions, so a bad configuration cannot open a drawer.
        return command in self._MATRIX.get(role, set())
