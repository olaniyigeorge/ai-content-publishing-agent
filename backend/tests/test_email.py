"""app/email.py — the Resend OTP send path had zero coverage (audit finding)."""

import resend

from app import email as email_module


def test_send_otp_email_calls_resend_with_expected_recipient_and_code(monkeypatch):
    sent = {}

    def fake_send(payload):
        sent.update(payload)
        return {"id": "fake"}

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))
    monkeypatch.setattr(email_module.get_settings(), "resend_api_key", "test-key", raising=False)

    email_module.send_otp_email("person@koyatalent.com", "123456")

    assert sent["to"] == ["person@koyatalent.com"]
    assert "123456" in sent["html"]


def test_send_otp_email_does_not_raise_when_resend_fails(monkeypatch):
    def fake_send(payload):
        raise RuntimeError("resend is down")

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))

    # Should log and swallow, never propagate an email-provider failure up
    # into request_code() and surface it to an end user.
    email_module.send_otp_email("person@koyatalent.com", "123456")
