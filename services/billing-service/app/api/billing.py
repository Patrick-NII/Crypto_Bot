"""Billing API — Stripe checkout, webhooks, and subscription management."""

from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

stripe.api_key = settings.STRIPE_SECRET_KEY


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateCheckoutRequest(BaseModel):
    user_id: str
    email: str
    plan: str = Field(..., pattern=r"^(pro|enterprise)$")


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class PortalRequest(BaseModel):
    stripe_customer_id: str


class PortalResponse(BaseModel):
    portal_url: str


class SubscriptionStatus(BaseModel):
    plan: str
    status: str
    current_period_end: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(req: CreateCheckoutRequest) -> CheckoutResponse:
    """Create a Stripe Checkout session for subscription."""
    price_id = (
        settings.STRIPE_PRICE_PRO if req.plan == "pro"
        else settings.STRIPE_PRICE_ENTERPRISE
    )

    if not price_id:
        raise HTTPException(status_code=400, detail=f"Stripe price not configured for plan: {req.plan}")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=req.email,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{settings.FRONTEND_URL}/dashboard?checkout=success",
            cancel_url=f"{settings.FRONTEND_URL}/pricing?checkout=cancelled",
            metadata={"user_id": req.user_id, "plan": req.plan},
            payment_method_types=["card"],
        )
        return CheckoutResponse(checkout_url=session.url or "", session_id=session.id)
    except stripe.StripeError as e:
        logger.error("Stripe checkout error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/portal", response_model=PortalResponse)
async def create_portal(req: PortalRequest) -> PortalResponse:
    """Create a Stripe Customer Portal session for self-service subscription management."""
    try:
        session = stripe.billing_portal.Session.create(
            customer=req.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/dashboard",
        )
        return PortalResponse(portal_url=session.url)
    except stripe.StripeError as e:
        logger.error("Stripe portal error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.SignatureVerificationError) as e:
        logger.warning("Webhook signature failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        plan = data.get("metadata", {}).get("plan", "pro")
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        logger.info("Checkout complete: user=%s plan=%s customer=%s", user_id, plan, customer_id)
        # TODO: Update subscription in database

    elif event_type == "customer.subscription.updated":
        logger.info("Subscription updated: %s status=%s", data.get("id"), data.get("status"))
        # TODO: Update subscription status in database

    elif event_type == "customer.subscription.deleted":
        logger.info("Subscription cancelled: %s", data.get("id"))
        # TODO: Downgrade user to free plan

    elif event_type == "invoice.payment_failed":
        logger.warning("Payment failed for customer: %s", data.get("customer"))
        # TODO: Mark subscription as past_due

    return {"status": "ok"}
