"""Helpers for keeping personal data out of logs."""


def mask_email(email: str) -> str:
    """ioannis@example.com -> io***@example.com

    Enough to spot patterns (same address, same domain) in the logs without storing
    the address itself: even a mistyped email is personal data.
    """
    local, _, domain = email.partition("@")
    return f"{local[:2]}***@{domain}"
