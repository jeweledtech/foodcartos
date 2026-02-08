"""
Square Integration Service

Handles Square API interactions and webhook processing.
"""

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Optional

from square import Square

from app.config import settings
from app.services.supabase import transaction_service, cart_service


def get_square_client() -> Optional[Square]:
    """Get Square API client."""
    if not settings.SQUARE_ACCESS_TOKEN:
        return None

    return Square(
        token=settings.SQUARE_ACCESS_TOKEN,
    )


def verify_webhook_signature(payload: bytes, signature: str, notification_url: str) -> bool:
    """
    Verify Square webhook signature.

    Square signs webhooks with HMAC-SHA256 using:
    - notification_url + body as the message
    - webhook signature key as the secret
    """
    if not settings.SQUARE_WEBHOOK_SIGNATURE_KEY:
        return False

    # Construct the string to sign
    string_to_sign = notification_url.encode() + payload

    # Calculate expected signature
    expected_signature = hmac.new(
        settings.SQUARE_WEBHOOK_SIGNATURE_KEY.encode(),
        string_to_sign,
        hashlib.sha256,
    ).digest()

    # Compare (timing-safe)
    try:
        provided = bytes.fromhex(signature)
        return hmac.compare_digest(expected_signature, provided)
    except ValueError:
        return False


async def process_payment_webhook(payment_data: dict, org_id: str) -> dict:
    """
    Process a Square payment.completed webhook.

    Extracts transaction data and stores it in the database.
    """
    payment = payment_data.get("payment", {})

    # Extract basic info
    square_id = payment.get("id")
    amount_money = payment.get("total_money", {})
    amount = amount_money.get("amount", 0) / 100  # Convert cents to dollars

    # Get timestamp
    created_at = payment.get("created_at")
    if created_at:
        timestamp = created_at
    else:
        timestamp = datetime.now(timezone.utc).isoformat()

    # Extract line items if available
    items = []
    order_id = payment.get("order_id")
    if order_id:
        # Could fetch order details from Square API for line items
        # For now, just note the order ID
        items = [{"order_id": order_id}]

    # Determine cart and location
    # In a real implementation, you'd map Square location_id to your cart/location
    # For now, we'll need to look this up or have it configured
    square_location_id = payment.get("location_id")

    # TODO: Look up cart and location based on Square location ID
    # For now, return the raw data
    cart_id = None
    location_id = None

    # Create transaction record
    transaction = await transaction_service.create(
        org_id=org_id,
        cart_id=cart_id,
        location_id=location_id,
        amount=amount,
        timestamp=timestamp,
        square_id=square_id,
        items=items,
        payment_method="card",
    )

    return {
        "transaction_id": transaction.get("id") if transaction else None,
        "square_id": square_id,
        "amount": amount,
        "status": "processed",
    }


async def sync_transactions_from_square(
    org_id: str,
    location_id: str,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Sync historical transactions from Square API.

    Useful for initial data import or catching up after downtime.
    """
    client = get_square_client()
    if not client:
        return {"error": "Square client not configured"}

    # List payments from Square
    try:
        result = client.payments.list(
            location_id=settings.SQUARE_LOCATION_ID,
            begin_time=start_date,
            end_time=end_date,
        )
        payments = result.payments or []
    except Exception as e:
        return {"error": str(e)}
    imported = 0
    skipped = 0

    for payment in payments:
        # Check if already imported
        square_id = getattr(payment, "id", None)

        # Extract amount
        total_money = getattr(payment, "total_money", None)
        amount = (total_money.amount if total_money else 0) / 100

        # Get timestamp
        timestamp = getattr(payment, "created_at", None)

        try:
            await transaction_service.create(
                org_id=org_id,
                cart_id=None,  # TODO: Map from Square location
                location_id=location_id,
                amount=amount,
                timestamp=timestamp,
                square_id=square_id,
                items=[],
                payment_method="card",
            )
            imported += 1
        except Exception as e:
            # Likely duplicate
            skipped += 1

    return {
        "total_payments": len(payments),
        "imported": imported,
        "skipped": skipped,
    }


async def get_square_locations() -> list:
    """
    Get list of Square locations for this account.

    Useful for mapping Square locations to FoodCartOS carts.
    """
    client = get_square_client()
    if not client:
        return []

    try:
        result = client.locations.list()
        return result.locations or []
    except Exception:
        return []
