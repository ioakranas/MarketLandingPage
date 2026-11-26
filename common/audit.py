"""Security audit events: who did what, from where, with which outcome.

One logger ("audit") so these lines can be routed and retained separately from
technical logs (e.g. to a SIEM). Event names are stable, dotted identifiers that
dashboards and alerts can match on ("login.failed").

Never pass passwords, tokens, session ids, names, phone numbers or full email addresses:
use user_id, or common.privacy.mask_email for addresses without an account.
"""

import logging

audit_logger = logging.getLogger("audit")


def audit(event: str, *, level: int = logging.INFO, **fields) -> None:
    audit_logger.log(level, event, extra={"event": event, **fields})
