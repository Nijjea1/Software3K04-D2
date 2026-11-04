"""Module 1.3.5  UI Presentation.

Responsibility : turn system outcomes into what the user reads.
Secret         : screen layout and wording.

Implements NFR-USA-01, NFR-USA-02, NFR-USA-04.

Every outcome is rendered with a text label, never colour alone, which is
NFR-USA-01. Every denial names an actionable next step and never echoes a
credential, which is NFR-USA-02.

Anticipated change: the screen is replaced, or the interface is translated.
Only this module changes.
"""
from typing import Optional


class UiPresentation:
    # Text labels, not colours. A colour-blind user reads the same outcome,
    # which is NFR-USA-01.
    _OUTCOME_LABEL = {
        "COMPLETED": "[COMPLETED]",
        "DENIED": "[DENIED]",
        "UNCERTAIN": "[UNCERTAIN]",
    }

    # Every denial reason the system can produce has an entry here, so no
    # message is a dead end. NFR-USA-02.
    _NEXT_STEP = {
        "role_not_permitted": "Ask a user with the required role to perform this action.",
        "mode_blocks": "Dispensing is disabled in this mode. Ask a technician to clear the fault.",
        "insufficient_stock": "Reduce the requested quantity or ask pharmacy to replenish.",
        "unknown_item": "Check the medication identifier and try again.",
        "drawer_inhibited": "This drawer is out of service. Ask a technician.",
        "drawer_already_open": "Another drawer is still open. Close it before starting a new dispense.",
        "no_session": "Present your credential to start a session.",
        "session_expired": "Your session timed out. Present your credential again.",
        "bad_credential": "Credential not recognised. Try again or contact pharmacy.",
        "removal_unconfirmed": "Removal could not be confirmed. Pharmacy must reconcile this transaction.",
    }

    def confirmation_screen(self, item_id: str, qty: int, drawer_id: str) -> str:
        """NFR-USA-04. Shown before any unlock is commanded."""
        return ("CONFIRM DISPENSE\n"
                "  medication : %s\n"
                "  quantity   : %d\n"
                "  drawer     : %s\n"
                "  Confirm to unlock. Cancel to abort." % (item_id, qty, drawer_id))

    def outcome(self, status: str, reason: Optional[str] = None) -> str:
        label = self._OUTCOME_LABEL.get(status, "[%s]" % status)
        if reason is None:
            return label + " " + status.title()
        # The fallback matters. An unmapped reason still gives the user
        # something to do rather than a blank screen.
        step = self._NEXT_STEP.get(reason, "Contact pharmacy.")
        return "%s %s\n  reason    : %s\n  next step : %s" % (
            label, status.title(), reason.replace("_", " "), step)

    def mode_banner(self, mode_name: str, link_name: str, pending: int) -> str:
        offline = "  OFFLINE, %d message(s) stored" % pending if link_name != "ONLINE" else ""
        return "MODE: %s   LINK: %s%s" % (mode_name, link_name, offline)
