
"""Alert delivery helper with duplicate-alert prevention."""


def send_notice_alert(text, deduplicator, sender):
    """Send a notice and record success only after delivery succeeds."""
    if not deduplicator.needs_alert(text):
        return "not_pending"

    delivered = sender(text)

    if delivered is not True:
        return "failed"

    deduplicator.mark_alerted(text)
    return "sent"
