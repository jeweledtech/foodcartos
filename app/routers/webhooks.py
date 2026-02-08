"""
Webhooks Router

Handles incoming webhooks from external services:
- Square (payment events)
- Twilio (SMS responses)
- n8n (workflow triggers)
- Meta (Instagram/Facebook verification)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request, status

logger = logging.getLogger(__name__)

from app.config import settings
from app.services.square import verify_webhook_signature, process_payment_webhook
from app.services.supabase import transaction_service, organization_service, order_service
from app.services.delivery_platforms import (
    doordash_service,
    ubereats_service,
    grubhub_service,
    sms_preorder_service,
)

router = APIRouter()


# ===========================================
# Square Webhooks
# ===========================================


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
        if not verify_webhook_signature(body, x_square_signature, notification_url):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Square signature",
            )

    # Parse payload
    payload = await request.json()

    event_type = payload.get("type")
    data = payload.get("data", {}).get("object", {})

    # Get merchant/org info from webhook
    merchant_id = payload.get("merchant_id")

    # TODO: Look up org_id from merchant_id mapping
    # For now, use a default or first org
    orgs = await organization_service.list_all()
    org_id = orgs[0]["id"] if orgs else None

    if not org_id:
        return {"status": "ignored", "reason": "No organization found"}

    if event_type == "payment.completed":
        result = await process_payment_webhook(data, org_id)
        return {"status": "processed", **result}

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


@router.post("/square/test")
async def square_test_webhook(request: Request):
    """
    Test endpoint for Square webhooks (no signature verification).

    Use this for testing in development.
    """
    payload = await request.json()

    # Get first org for testing
    orgs = await organization_service.list_all()
    org_id = orgs[0]["id"] if orgs else None

    if not org_id:
        return {"status": "error", "reason": "No organization found. Run seed script first."}

    event_type = payload.get("type", "payment.completed")
    data = payload.get("data", {}).get("object", payload)

    if event_type == "payment.completed":
        result = await process_payment_webhook(data, org_id)
        return {"status": "processed", **result}

    return {"status": "received", "event": event_type}


# ===========================================
# Twilio Webhooks
# ===========================================


@router.post("/twilio/sms")
async def twilio_sms_webhook(request: Request):
    """
    Handle incoming SMS from Twilio.

    Processes customer responses using SMS pre-order service:
    - "ORDER" - Send menu and start pre-order flow
    - "STOP" - Unsubscribe
    - "HELP" - Send help message
    - Other text - Parse as order (e.g., "2 dirty dogs, 1 drink")
    """
    # Parse form data (Twilio sends as form, not JSON)
    form_data = await request.form()

    from_number = form_data.get("From")
    body = form_data.get("Body", "").strip()
    to_number = form_data.get("To")

    # Get org for this phone number (TODO: map from Twilio number)
    orgs = await organization_service.list_all()
    org_id = orgs[0]["id"] if orgs else None

    if not org_id:
        return {"status": "ignored", "reason": "No organization found"}

    # Use SMS pre-order service to handle the message
    result = await sms_preorder_service.handle_incoming_sms(
        from_number=from_number,
        body=body,
        org_id=org_id,
    )

    # If an order was parsed, save it
    if result.get("action") == "order_received" and result.get("order"):
        order = result["order"]

        # Save order to database
        saved_order = await order_service.create(**order.to_dict())

        if saved_order:
            # Confirm the order via SMS
            order.id = saved_order["id"]
            await sms_preorder_service.confirm_order(order)

            return {
                "status": "order_created",
                "order_id": saved_order["id"],
                "from": from_number,
            }

    return result


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
# Delivery Platform Webhooks
# ===========================================


@router.post("/doordash")
async def doordash_webhook(
    request: Request,
    x_doordash_signature: Optional[str] = Header(None, alias="X-DoorDash-Signature"),
):
    """
    Handle DoorDash order webhooks.

    Events:
    - order.created: New order from DoorDash marketplace
    - order.status_updated: Order status changed
    - delivery.status_updated: Driver status update
    """
    body = await request.body()

    # Verify signature in production
    if settings.APP_ENV == "production":
        if not x_doordash_signature:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
        if not doordash_service.verify_webhook(body, x_doordash_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload = await request.json()
    event_type = payload.get("event_type", "")

    # Get org (TODO: map from DoorDash store ID)
    orgs = await organization_service.list_all()
    org_id = orgs[0]["id"] if orgs else None

    if not org_id:
        return {"status": "ignored", "reason": "No organization found"}

    if event_type == "order.created":
        order = doordash_service.parse_order(payload)
        order.org_id = org_id

        # Save to database
        saved_order = await order_service.create(**order.to_dict())

        return {"status": "processed", "order_id": saved_order.get("id") if saved_order else None}

    elif event_type in ["order.status_updated", "delivery.status_updated"]:
        # Update existing order
        external_id = payload.get("external_delivery_id")
        existing = await order_service.get_by_external_id("doordash", external_id)
        if existing:
            order = doordash_service.parse_order(payload)
            await order_service.update_status(existing["id"], order.status.value)

        return {"status": "processed", "event": event_type}

    return {"status": "ignored", "event": event_type}


@router.post("/ubereats")
async def ubereats_webhook(
    request: Request,
    x_uber_signature: Optional[str] = Header(None, alias="X-Uber-Signature"),
):
    """
    Handle UberEats order webhooks.

    Events:
    - orders.notification: New order or order update
    """
    body = await request.body()

    # Verify signature in production
    if settings.APP_ENV == "production":
        if not x_uber_signature:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
        if not ubereats_service.verify_webhook(body, x_uber_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload = await request.json()
    event_type = payload.get("event_type", "")

    # Get org (TODO: map from UberEats store ID)
    orgs = await organization_service.list_all()
    org_id = orgs[0]["id"] if orgs else None

    if not org_id:
        return {"status": "ignored", "reason": "No organization found"}

    if event_type == "orders.notification":
        order = ubereats_service.parse_order(payload)
        order.org_id = org_id

        # Check if order exists
        existing = await order_service.get_by_external_id("ubereats", order.external_id)

        if existing:
            # Update existing order
            await order_service.update_status(existing["id"], order.status.value)
            return {"status": "updated", "order_id": existing["id"]}
        else:
            # Create new order
            saved_order = await order_service.create(**order.to_dict())
            return {"status": "created", "order_id": saved_order.get("id") if saved_order else None}

    return {"status": "ignored", "event": event_type}


@router.post("/grubhub")
async def grubhub_webhook(
    request: Request,
    x_grubhub_signature: Optional[str] = Header(None, alias="X-Grubhub-Signature"),
):
    """
    Handle Grubhub order webhooks.
    """
    body = await request.body()

    # Verify signature in production
    if settings.APP_ENV == "production":
        if not x_grubhub_signature:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
        if not grubhub_service.verify_webhook(body, x_grubhub_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload = await request.json()
    event_type = payload.get("event_type", "order.new")

    # Get org (TODO: map from Grubhub restaurant ID)
    orgs = await organization_service.list_all()
    org_id = orgs[0]["id"] if orgs else None

    if not org_id:
        return {"status": "ignored", "reason": "No organization found"}

    if event_type in ["order.new", "order.created"]:
        order = grubhub_service.parse_order(payload)
        order.org_id = org_id

        saved_order = await order_service.create(**order.to_dict())
        return {"status": "processed", "order_id": saved_order.get("id") if saved_order else None}

    elif event_type == "order.status_updated":
        external_id = payload.get("order_id")
        existing = await order_service.get_by_external_id("grubhub", external_id)
        if existing:
            order = grubhub_service.parse_order(payload)
            await order_service.update_status(existing["id"], order.status.value)

        return {"status": "processed", "event": event_type}

    return {"status": "ignored", "event": event_type}


# ===========================================
# Meta Webhooks (Instagram / Facebook)
# ===========================================


@router.get("/meta")
async def meta_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Meta webhook verification (GET challenge).

    Required by Meta to register webhook URLs for Instagram and Facebook.
    Meta sends a GET with hub.mode=subscribe, hub.verify_token, and hub.challenge.
    We verify the token and echo back the challenge.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.SECRET_KEY:
        return int(hub_challenge)

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@router.post("/meta")
async def meta_webhook_event(request: Request):
    """
    Handle Meta webhook events (Instagram/Facebook).

    Events include: comments, mentions, story insights, etc.
    """
    payload = await request.json()
    object_type = payload.get("object")  # "instagram" or "page"
    entries = payload.get("entry", [])

    # Log the event for now — specific handling can be added later
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            field = change.get("field")
            logger.info("Meta webhook: %s/%s", object_type, field)

    return {"status": "received"}


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
        "records_processed": len(data) if isinstance(data, list) else 1,
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
            "sync_interval_seconds": settings.SYNC_INTERVAL_SECONDS,
            "gps_interval_seconds": settings.GPS_UPDATE_INTERVAL_SECONDS,
            "api_url": settings.API_BASE_URL,
        },
    }
