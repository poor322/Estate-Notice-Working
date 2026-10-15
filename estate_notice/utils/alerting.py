
"""Alert delivery helpers with duplicate-alert prevention."""


def send_notice_alert(text, deduplicator, sender):
    """Send a notice and record success only after delivery succeeds."""
    if not deduplicator.needs_alert(text):
        return "not_pending"

    delivered = sender(text)

    if delivered is not True:
        return "failed"

    deduplicator.mark_alerted(text)
    return "sent"


def process_pending_alerts(notices, deduplicator, sender):
    """Attempt delivery for registered notices that still need an alert."""
    results = []

    for notice in notices:
        text = notice.get("text", "").strip()

        if not text:
            results.append("invalid")
            continue

        if not deduplicator.is_duplicate(text):
            results.append("not_registered")
    continue

        result = send_notice_alert(text, deduplicator, sender)
        results.append(result)

    return results
