"""Email delivery service supporting Resend REST API and standard SMTP."""

from __future__ import annotations

import html
import logging
import smtplib
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Tuple
import requests

from app.config import settings

logger = logging.getLogger("nft_trend_analyzer.email")


class EmailService:
    """Dispatches transactional emails out-of-band using configured providers."""

    @staticmethod
    def send_password_reset_email(
        to_email: str,
        reset_token: str,
        frontend_url: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Send password reset instructions containing the secure reset token and out-of-band link.

        Security guarantees:
        - NEVER logs the token.
        - Fails safely without exposing token or internal secrets in error strings.
        - Token is delivered out-of-band only.
        - Escapes HTML values and encodes URL query parameters safely.
        """
        clean_email = to_email.strip().lower()
        base_url = (frontend_url or settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
        encoded_token = urllib.parse.quote(reset_token)
        reset_link = f"{base_url}/reset-password?token={encoded_token}"

        safe_email_html = html.escape(clean_email)
        safe_link_html = html.escape(reset_link)
        safe_token_html = html.escape(reset_token)

        subject = "Reset Your NFT Trend Analyzer Password"
        text_content = (
            f"Hello,\n\n"
            f"A password reset request was initiated for your NFT Trend Analyzer account.\n\n"
            f"To choose a new password, click the link below or copy and paste it into your browser:\n"
            f"{reset_link}\n\n"
            f"If you are using the manual token entry interface, your authorization token is:\n"
            f"{reset_token}\n\n"
            f"This token is valid for 1 hour and can only be used once.\n"
            f"If you did not request this change, please ignore this email.\n\n"
            f"Best regards,\n"
            f"The NFT Trend Analyzer Security Team"
        )
        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 40px 20px;">
  <div style="max-width: 560px; margin: 0 auto; background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px;">
    <h2 style="color: #ffffff; margin-top: 0;">Password Reset Request</h2>
    <p style="color: #94a3b8; font-size: 14px; line-height: 1.6;">A password reset request was initiated for your NFT Trend Analyzer account (<code>{safe_email_html}</code>).</p>
    <div style="text-align: center; margin: 32px 0;">
      <a href="{safe_link_html}" style="display: inline-block; background-color: #6366f1; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 8px; font-weight: 600; font-size: 14px;">Reset Password</a>
    </div>
    <p style="color: #94a3b8; font-size: 13px; line-height: 1.6;">Or enter this authorization token directly in the reset interface:</p>
    <div style="background-color: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 13px; color: #38bdf8; word-break: break-all;">
      {safe_token_html}
    </div>
    <p style="color: #64748b; font-size: 12px; margin-top: 24px; line-height: 1.5;">This token expires in 1 hour and can only be used once. If you did not request this reset, no action is required.</p>
  </div>
</body>
</html>"""

        # 1. Dispatch via Resend REST API (if EMAIL_PROVIDER_API_KEY configured)
        if settings.EMAIL_PROVIDER_API_KEY:
            try:
                res = requests.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {settings.EMAIL_PROVIDER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": settings.EMAIL_FROM,
                        "to": [clean_email],
                        "subject": subject,
                        "text": text_content,
                        "html": html_content,
                    },
                    timeout=8.0,
                )
                if res.status_code in (200, 201):
                    logger.info("Password reset email sent successfully via Resend API to %s", clean_email)
                    return True, "Email dispatched successfully via provider."
                logger.error("Resend API rejected dispatch (HTTP %d)", res.status_code)
                return False, f"Email delivery provider returned HTTP {res.status_code}"
            except Exception as exc:
                logger.error("Network failure contacting Resend API: %s", type(exc).__name__)
                return False, f"Email delivery provider network error: {type(exc).__name__}"

        # 2. Dispatch via SMTP (if SMTP_HOST configured)
        if settings.SMTP_HOST:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = settings.EMAIL_FROM
                msg["To"] = clean_email
                msg.attach(MIMEText(text_content, "plain"))
                msg.attach(MIMEText(html_content, "html"))

                if settings.SMTP_PORT == 465:
                    server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0)
                else:
                    server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0)
                    server.starttls()

                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

                server.sendmail(settings.EMAIL_FROM, [clean_email], msg.as_string())
                server.quit()
                logger.info("Password reset email sent successfully via SMTP to %s", clean_email)
                return True, "Email dispatched successfully via SMTP."
            except Exception as exc:
                logger.error("SMTP delivery failure: %s", type(exc).__name__)
                return False, f"SMTP delivery error: {type(exc).__name__}"

        # 3. No provider configured
        return False, "No email delivery provider configured."

    @staticmethod
    def send_admin_verification_email(
        to_email: str,
        verification_token: str,
        frontend_url: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Send administrator application verification instructions with out-of-band link.

        Security guarantees:
        - NEVER logs the token.
        - Fails safely without exposing token or internal secrets in error strings.
        - Token is delivered out-of-band only.
        - Escapes HTML values and encodes URL query parameters safely.
        - Does NOT mark an admin email verified before successful token verification.
        """
        clean_email = to_email.strip().lower()
        base_url = (frontend_url or settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
        encoded_token = urllib.parse.quote(verification_token)
        encoded_email = urllib.parse.quote(clean_email)
        verify_link = f"{base_url}/admin/register?token={encoded_token}&email={encoded_email}"

        safe_email_html = html.escape(clean_email)
        safe_verify_link_html = html.escape(verify_link)
        safe_token_html = html.escape(verification_token)

        subject = "Verify Your Administrator Application — NFT Trend Analyzer"
        text_content = (
            f"Hello,\n\n"
            f"An administrator registration request was submitted for your Gmail address ({clean_email}).\n\n"
            f"To verify email ownership and make your application eligible for administrator review, "
            f"please click the link below or paste it into your browser:\n"
            f"{verify_link}\n\n"
            f"Alternatively, enter this verification token on the verification page:\n"
            f"{verification_token}\n\n"
            f"This token is valid for 24 hours and can only be used once.\n"
            f"After email verification, an active administrator must review and approve your application "
            f"before your administrator credentials become active.\n\n"
            f"If you did not request administrator access, please disregard this email.\n\n"
            f"Best regards,\n"
            f"The NFT Trend Analyzer Security Team"
        )
        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #070b14; color: #f8fafc; padding: 40px 20px;">
  <div style="max-width: 560px; margin: 0 auto; background-color: #0a0f1d; border: 1px solid #f59e0b; border-radius: 12px; padding: 32px;">
    <h2 style="color: #ffffff; margin-top: 0;">Administrator Application Verification</h2>
    <p style="color: #94a3b8; font-size: 14px; line-height: 1.6;">An administrator access request was initiated for <code>{safe_email_html}</code>.</p>
    <p style="color: #94a3b8; font-size: 13px; line-height: 1.6;">Please confirm email ownership to advance your application to pending administrator review:</p>
    <div style="text-align: center; margin: 32px 0;">
      <a href="{safe_verify_link_html}" style="display: inline-block; background-color: #f59e0b; color: #0f172a; text-decoration: none; padding: 12px 28px; border-radius: 8px; font-weight: 700; font-size: 14px;">Verify Email Address</a>
    </div>
    <p style="color: #94a3b8; font-size: 13px; line-height: 1.6;">Or enter this verification token directly into the registration portal:</p>
    <div style="background-color: #030712; border: 1px solid #374151; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 13px; color: #fbbf24; word-break: break-all;">
      {safe_token_html}
    </div>
    <p style="color: #64748b; font-size: 12px; margin-top: 24px; line-height: 1.5;">This single-use token expires in 24 hours. After email verification, an active administrator must approve your application before login is permitted.</p>
  </div>
</body>
</html>"""

        # 1. Dispatch via Resend REST API (if EMAIL_PROVIDER_API_KEY configured)
        if settings.EMAIL_PROVIDER_API_KEY:
            try:
                res = requests.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {settings.EMAIL_PROVIDER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": settings.EMAIL_FROM,
                        "to": [clean_email],
                        "subject": subject,
                        "text": text_content,
                        "html": html_content,
                    },
                    timeout=8.0,
                )
                if res.status_code in (200, 201):
                    logger.info("Admin verification email sent successfully via Resend API to %s", clean_email)
                    return True, "Email dispatched successfully via provider."
                logger.error("Resend API rejected dispatch (HTTP %d)", res.status_code)
                return False, f"Email delivery provider returned HTTP {res.status_code}"
            except Exception as exc:
                logger.error("Network failure contacting Resend API: %s", type(exc).__name__)
                return False, f"Email delivery provider network error: {type(exc).__name__}"

        # 2. Dispatch via SMTP (if SMTP_HOST configured)
        if settings.SMTP_HOST:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = settings.EMAIL_FROM
                msg["To"] = clean_email
                msg.attach(MIMEText(text_content, "plain"))
                msg.attach(MIMEText(html_content, "html"))

                if settings.SMTP_PORT == 465:
                    server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0)
                else:
                    server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0)
                    server.starttls()

                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

                server.sendmail(settings.EMAIL_FROM, [clean_email], msg.as_string())
                server.quit()
                logger.info("Admin verification email sent successfully via SMTP to %s", clean_email)
                return True, "Email dispatched successfully via SMTP."
            except Exception as exc:
                logger.error("SMTP delivery failure: %s", type(exc).__name__)
                return False, f"SMTP delivery error: {type(exc).__name__}"

        # 3. No provider configured
        return False, "No email delivery provider configured."
