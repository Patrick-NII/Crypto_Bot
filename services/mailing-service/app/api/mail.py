"""Mail API — send emails using templates."""

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


TEMPLATE_SUBJECTS = {
    "verify_email": "Verify your Okamoey account",
    "password_reset": "Reset your Okamoey password",
    "welcome": "Welcome to Okamoey!",
    "alert_triggered": "Alert triggered: {symbol}",
    "weekly_report": "Your weekly trading report",
}


class SendMailRequest(BaseModel):
    to: EmailStr
    template: str = Field(..., description="Template name (e.g. verify_email)")
    data: dict[str, Any] = Field(default_factory=dict)
    subject: str | None = None


class SendMailResponse(BaseModel):
    status: str
    message: str


@router.post("/send", response_model=SendMailResponse)
async def send_mail(req: SendMailRequest) -> SendMailResponse:
    """Render a template and send an email."""
    # Resolve subject
    subject = req.subject or TEMPLATE_SUBJECTS.get(req.template, "Okamoey Notification")
    if "{" in subject:
        subject = subject.format(**req.data)

    # Render template
    try:
        tpl = _jinja.get_template(f"{req.template}.html")
        html_body = tpl.render(**req.data)
    except TemplateNotFound:
        raise HTTPException(status_code=400, detail=f"Unknown template: {req.template}")

    # Build email
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
    msg["To"] = req.to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    # Send via SMTP
    if not settings.SMTP_USER:
        logger.warning("SMTP not configured — email to %s skipped", req.to)
        return SendMailResponse(status="skipped", message="SMTP not configured")

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_USE_TLS,
        )
        logger.info("Email sent to %s (template=%s)", req.to, req.template)
        return SendMailResponse(status="sent", message=f"Email sent to {req.to}")
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return SendMailResponse(status="failed", message=str(e))
