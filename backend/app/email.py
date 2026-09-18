"""Transactional email via Resend.

Always prints the OTP to stdout in development regardless of whether Resend
is configured, so local/dev workflows never require a working email
provider to log in.
"""

import logging

import resend

from app.config import get_settings

logger = logging.getLogger(__name__)


def send_otp_email(email: str, code: str) -> None:
    settings = get_settings()

    if settings.environment == "development":
        print(f"[dev-only] OTP for {email}: {code}")

    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — skipping OTP email send to %s", email)
        return

    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send(
            {
                "from": f"{settings.email_from_name} <{settings.email_from_address}>",
                "to": [email],
                "subject": "Your sign-in code",
                "html": (
                    f"<p>Your sign-in code is:</p>"
                    f"<p style='font-size:24px;font-weight:bold;letter-spacing:4px'>{code}</p>"
                    f"<p>This code expires in {settings.otp_ttl_minutes} minutes. "
                    f"If you didn't request this, you can ignore this email.</p>"
                ),
            }
        )
    except Exception:
        logger.exception("failed to send OTP email to %s", email)


def send_review_ready_email(content_request_id: str, raw_idea: str | None) -> None:
    """Notify the reviewer inbox that a content request just landed in
    in_review and is waiting on a human decision."""
    settings = get_settings()

    if not settings.reviewer_notification_email:
        logger.warning(
            "REVIEWER_NOTIFICATION_EMAIL not set — skipping review-ready email for request %s", content_request_id
        )
        return

    if not settings.resend_api_key:
        logger.warning(
            "RESEND_API_KEY not set — skipping review-ready email for request %s", content_request_id
        )
        return

    resend.api_key = settings.resend_api_key
    subject_idea = raw_idea or "(untitled request)"
    try:
        resend.Emails.send(
            {
                "from": f"{settings.email_from_name} <{settings.email_from_address}>",
                "to": [settings.reviewer_notification_email],
                "subject": f"Ready for review: {subject_idea}",
                "html": (
                    f"<p>A content request is waiting for review:</p>"
                    f"<p><strong>{subject_idea}</strong></p>"
                    f"<p>Request ID: {content_request_id}</p>"
                ),
            }
        )
    except Exception:
        logger.exception("failed to send review-ready email for request %s", content_request_id)
