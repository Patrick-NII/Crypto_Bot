"""Mail API — send emails using templates via Hostinger SMTP.

Two mailboxes:
  - support@gluetrade.com  → transactional (verify, reset, security)
  - hello@gluetrade.com    → communication (welcome, alerts, reports)
"""

from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiosmtplib
from fastapi import APIRouter, HTTPException
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mail", tags=["mail"])

# Jinja2 template loader
import os
_template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_jinja = Environment(loader=FileSystemLoader(_template_dir), autoescape=True)


# ── Template → subject mapping ──
TEMPLATE_SUBJECTS: dict[str, str] = {
    "verify_email": "Verify your GlueTrade account",
    "password_reset": "Reset your GlueTrade password",
    "welcome": "Welcome to GlueTrade!",
    "alert_triggered": "Alert triggered: {symbol}",
    "weekly_report": "Your weekly trading report",
    "security_alert": "Security alert on your GlueTrade account",
    "login_notification": "New login to your GlueTrade account",
    "trade_buy_confirmation": "Achat exécuté : {quantity} {symbol}",
    "trade_sell_confirmation": "Vente exécutée : {quantity} {symbol}",
    "deposit_confirmation": "Dépôt détecté : +{amount} {asset}",
    "withdrawal_confirmation": "Retrait détecté : -{amount} {asset}",
    "daily_recap": "Votre récap GlueTrade du {recap_date}",
}

# ── Template → mailbox mapping (auto-select sender) ──
_SUPPORT_TEMPLATES = {
    "verify_email",
    "password_reset",
    "security_alert",
    "login_notification",
    "withdrawal_confirmation",
}
_HELLO_TEMPLATES = {
    "welcome",
    "alert_triggered",
    "weekly_report",
    "trade_buy_confirmation",
    "trade_sell_confirmation",
    "deposit_confirmation",
    "daily_recap",
}


def _resolve_sender(template: str, explicit_sender: str | None) -> str:
    """Return 'support' or 'hello' based on template or explicit override."""
    if explicit_sender and explicit_sender in ("support", "hello"):
        return explicit_sender
    if template in _SUPPORT_TEMPLATES:
        return "support"
    if template in _HELLO_TEMPLATES:
        return "hello"
    return "support"  # default to no-reply for unknown templates


def _get_smtp_credentials(sender: str) -> tuple[str, str, str, str]:
    """Return (user, password, from_address, from_name) for the given sender."""
    if sender == "hello":
        return (
            settings.SMTP_HELLO_USER,
            settings.SMTP_HELLO_PASSWORD,
            settings.MAIL_FROM_HELLO,
            settings.MAIL_FROM_HELLO_NAME,
        )
    return (
        settings.SMTP_SUPPORT_USER,
        settings.SMTP_SUPPORT_PASSWORD,
        settings.MAIL_FROM_SUPPORT,
        settings.MAIL_FROM_SUPPORT_NAME,
    )


class SendMailRequest(BaseModel):
    to: EmailStr
    template: str = Field(..., description="Template name (e.g. verify_email)")
    data: dict[str, Any] = Field(default_factory=dict)
    subject: str | None = None
    sender: str | None = Field(None, description="Force sender: 'support' or 'hello'. Auto-detected from template if omitted.")


class SendMailResponse(BaseModel):
    status: str
    message: str
    sender: str = ""


@router.post("/send", response_model=SendMailResponse)
async def send_mail(req: SendMailRequest) -> SendMailResponse:
    """Render a template and send an email via the appropriate mailbox."""
    # Resolve sender
    sender = _resolve_sender(req.template, req.sender)
    smtp_user, smtp_password, mail_from, mail_from_name = _get_smtp_credentials(sender)

    # Resolve subject
    subject = req.subject or TEMPLATE_SUBJECTS.get(req.template, "GlueTrade Notification")
    if "{" in subject:
        try:
            subject = subject.format(**req.data)
        except KeyError:
            pass

    # Render template
    try:
        tpl = _jinja.get_template(f"{req.template}.html")
        html_body = tpl.render(**req.data)
    except TemplateNotFound:
        raise HTTPException(status_code=400, detail=f"Unknown template: {req.template}")

    # Build email
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{mail_from_name} <{mail_from}>"
    msg["To"] = req.to
    msg["Subject"] = subject
    msg["Reply-To"] = settings.MAIL_FROM_HELLO  # replies always go to hello@
    msg.attach(MIMEText(html_body, "html"))

    # Check credentials
    if not smtp_user or not smtp_password:
        logger.warning("SMTP credentials not configured for %s — email to %s skipped", sender, req.to)
        return SendMailResponse(status="skipped", message=f"SMTP not configured for {sender}", sender=sender)

    # Send via SMTP (SSL on port 465)
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=smtp_user,
            password=smtp_password,
            use_tls=settings.SMTP_USE_SSL,  # SSL (port 465), not STARTTLS
        )
        logger.info("Email sent to %s via %s (template=%s)", req.to, mail_from, req.template)
        return SendMailResponse(status="sent", message=f"Email sent to {req.to}", sender=sender)
    except Exception as e:
        logger.error("Failed to send email via %s: %s", mail_from, e)
        return SendMailResponse(status="failed", message=str(e), sender=sender)


@router.get("/health")
async def health():
    """Check if mailing service is up and SMTP is configured."""
    support_ok = bool(settings.SMTP_SUPPORT_USER and settings.SMTP_SUPPORT_PASSWORD)
    hello_ok = bool(settings.SMTP_HELLO_USER and settings.SMTP_HELLO_PASSWORD)
    return {
        "status": "ok",
        "smtp_host": settings.SMTP_HOST,
        "support_configured": support_ok,
        "hello_configured": hello_ok,
    }
