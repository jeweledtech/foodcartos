"""
Webhooks Router

Handles incoming webhooks from external services:
- Square (payment events)
- Twilio (SMS responses)
- n8n (workflow triggers)
"""

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.config import settings

router = APIRouter()


# ===========================================
# Square Webhooks
# ===========================================


def verify_square_signature(
    payload: bytes,
    signature: str,
    signature_key: str,
    notification_url: str,
) -> bool:
    """
    Verify Square webhook signature.

    Square signs webhooks with HMAC-SHA256.
    """
    # Construct the string to sign
    string_to_sign = notification_url.encode() + payload

    # Calculate expected signature
    expected_signature = hmac.new(
        signature_key.encode(),
        string_to_sign,
        hashlib.sha256,
    ).digest()

    # Compare (timing-safe)
    try:
        provided = bytes.fromhex(signature)
        return hmac.compare_digest(expected_signature, provided)
    except ValueError:
        return False


@router.post("/square")
async def square_webhook(
    request: Request,
    x_square_signature: Optional[str] = Header(None, alias="X-Square-Signature"),
):
    """
    Handle Square payment webhooks.

    Events handled:
    - payment.completed: New transaction
    - payment.updated: Transaction updated
    - refund.created: Refund processed

    Creates transaction records in the database.
    """
    # Get raw body for signature verification
    body = await request.body()

    # Verify signature in production
    if settings.APP_ENV == "production":
        if not x_square_signature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Square signature",
            )

        notification_url = str(request.url)
        if not verify_square_signature(
            body,
            x_square_signature,
            settings.SQUARE_WEBHOOK_SIGNATURE_KEY,
            notification_url,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Square signature",
            )

    # Parse payload
    payload = await request.json()

    event_type = payload.get("type")
    data = payload.get("data", {}).get("object", {})

    if event_type == "payment.completed":
        # Extract transaction data
        payment = data.get("payment", {})

        transaction = {
            "square_id": payment.get("id"),
            "amount": payment.get("total_money", {}).get("amount", 0) / 100,  # Convert cents
            "timestamp": datetime.now(timezone.utc),
            # TODO: Look up cart_id and location_id from Square location
        }

        # TODO: Save to database
        # TODO: Trigger n8n workflow for real-time updates

        return {"status": "processed", "transaction_id": transaction["square_id"]}

    elif event_type == "payment.updated":
        # Handle updates (tips added, etc.)
        # TODO: Update existing transaction
        return {"status": "processed", "event": "payment.updated"}

    elif event_type == "refund.created":
        # Handle refunds
        # TODO: Create refund record, update transaction
        return {"status": "processed", "event": "refund.created"}

    # Unknown event type - log but don't fail
    return {"status": "ignored", "event": event_type}


# ===========================================
# Twilio Webhooks
# ===========================================


@router.post("/twilio/sms")
async def twilio_sms_webhook(request: Request):
    """
    Handle incoming SMS from Twilio.

    Processes customer responses:
    - "ORDER" - Start pre-order flow
    - "STOP" - Unsubscribe
    - "HELP" - Send help message
    - Other - Forward to relevant workflow
    """
    # Parse form data (Twilio sends as form, not JSON)
    form_data = await request.form()

    from_number = form_data.get("From")
    body = form_data.get("Body", "").strip().upper()
    to_number = form_data.get("To")

    # Handle commands
    if body == "STOP":
        # Unsubscribe - Twilio handles this automatically
        # but we should update our records
        # TODO: Mark customer as unsubscribed
        return {"status": "unsubscribed"}

    elif body == "ORDER" or body.startswith("ORDER"):
        # Pre-order request
        # TODO: Trigger pre-order workflow in n8n
        return {
            "status": "order_initiated",
            "from": from_number,
        }

    elif body == "HELP":
        # Send help message
        # TODO: Send help response via Twilio
        return {"status": "help_sent"}

    else:
        # Unknown command - could be a reply to a conversation
        # TODO: Forward to n8n for processing
        return {
            "status": "received",
            "from": from_number,
            "body": body,
        }


@router.post("/twilio/status")
async def twilio_status_webhook(request: Request):
    """
    Handle SMS delivery status callbacks.

    Updates message delivery status for analytics.
    """
    form_data = await request.form()

    message_sid = form_data.get("MessageSid")
    message_status = form_data.get("MessageStatus")  # sent, delivered, failed, etc.

    # TODO: Update message record with delivery status

    return {"status": "processed", "message_sid": message_sid}


# ===========================================
# n8n Webhooks
# ===========================================


@router.post("/n8n/quality-complete")
async def n8n_quality_complete(request: Request):
    """
    Webhook called by n8n when quality checklist is complete.

    Used to update shift status and trigger downstream actions.
    """
    payload = await request.json()

    cart_id = payload.get("cart_id")
    employee_id = payload.get("employee_id")
    completion_time = payload.get("completion_time")

    # TODO: Update shift record
    # TODO: Calculate if on time or late

    return {
        "status": "processed",
        "cart_id": cart_id,
        "employee_id": employee_id,
    }


@router.post("/n8n/alert")
async def n8n_alert(request: Request):
    """
    Generic alert webhook from n8n.

    Receives alerts generated by n8n workflows for logging.
    """
    payload = await request.json()

    alert_type = payload.get("type")
    message = payload.get("message")
    data = payload.get("data", {})

    # TODO: Log alert to database
    # TODO: Could trigger additional actions based on alert type

    return {"status": "logged", "alert_type": alert_type}


# ===========================================
# Hardware Agent Webhooks
# ===========================================


@router.post("/agent/sync")
async def agent_sync(request: Request):
    """
    Receive sync data from cart hardware agent.

    The Raspberry Pi agent sends batched data:
    - Transactions (from local SQLite)
    - GPS pings
    - Quality check photos
    - System status
    """
    payload = await request.json()

    hardware_id = payload.get("hardware_id")
    sync_type = payload.get("type")  # transactions, gps, quality, status
    data = payload.get("data", [])

    # TODO: Validate hardware ID
    # TODO: Process sync data based on type
    # TODO: Return acknowledgment for processed records

    return {
        "status": "synced",
        "hardware_id": hardware_id,
        "records_processed": len(data),
    }


@router.post("/agent/register")
async def agent_register(request: Request):
    """
    Register new hardware agent.

    Called during initial cart setup to link hardware to organization.
    """
    payload = await request.json()

    hardware_id = payload.get("hardware_id")
    registration_code = payload.get("registration_code")

    # TODO: Validate registration code
    # TODO: Link hardware to cart record
    # TODO: Return configuration for agent

    return {
        "status": "registered",
        "hardware_id": hardware_id,
        "config": {
            "sync_interval_seconds": 60,
            "gps_interval_seconds": 300,
            "api_url": settings.API_BASE_URL,
        },
    }
