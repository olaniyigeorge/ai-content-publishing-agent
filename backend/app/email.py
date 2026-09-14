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
