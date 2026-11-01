"""Email delivery service supporting Resend REST API and standard SMTP."""

from __future__ import annotations

import logging
import smtplib
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
        """
        clean_email = to_email.strip().lower()
        base_url = (frontend_url or settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
        reset_link = f"{base_url}/reset-password?token={reset_token}"

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
    <p style="color: #94a3b8; font-size: 14px; line-height: 1.6;">A password reset request was initiated for your NFT Trend Analyzer account (<code>{clean_email}</code>).</p>
    <div style="text-align: center; margin: 32px 0;">
      <a href="{reset_link}" style="display: inline-block; background-color: #6366f1; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 8px; font-weight: 600; font-size: 14px;">Reset Password</a>
    </div>
    <p style="color: #94a3b8; font-size: 13px; line-height: 1.6;">Or enter this authorization token directly in the reset interface:</p>
    <div style="background-color: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 13px; color: #38bdf8; word-break: break-all;">
      {reset_token}
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
