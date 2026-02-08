"""
Grubhub Integration Service

Handles Grubhub Marketplace integration for receiving orders.

API Docs: https://developer.grubhub.com/
"""

from datetime import datetime
from typing import Optional

import httpx

from app.config import settings
from app.services.delivery_platforms.base import (
    DeliveryPlatform,
    DeliveryPlatformService,
    NormalizedOrder,
    OrderItem,
    OrderStatus,
    DeliveryInfo,
)


class GrubhubService(DeliveryPlatformService):
    """
    Grubhub integration for FoodCartOS.

    Handles:
    - Webhook verification
    - Order parsing from Grubhub format
    - Order status updates
    - Menu sync (future)
    """

    platform = DeliveryPlatform.GRUBHUB

    # API endpoints
    SANDBOX_URL = "https://api-gtm.grubhub.com"
    PRODUCTION_URL = "https://api-gtm.grubhub.com"

    def __init__(self):
        self.api_key = settings.GRUBHUB_API_KEY
        self.webhook_secret = settings.GRUBHUB_WEBHOOK_SECRET
        self.environment = settings.GRUBHUB_ENVIRONMENT

        self.base_url = self.PRODUCTION_URL if self.environment == "production" else self.SANDBOX_URL

    def _get_headers(self) -> dict:
        """Get headers for Grubhub API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def verify_webhook(self, payload: bytes, signature: str, **kwargs) -> bool:
        """
        Verify Grubhub webhook signature.

        Grubhub uses HMAC-SHA256 for webhook verification.
        """
        if not self.webhook_secret:
            return False

        return self._hmac_verify(
            payload=payload,
            signature=signature,
            secret=self.webhook_secret,
            algorithm="sha256",
        )

    def parse_order(self, payload: dict) -> NormalizedOrder:
        """
        Parse Grubhub order webhook into NormalizedOrder.
        """
        order_data = payload.get("order", payload)

        # Parse items
        items = []
        for line_item in order_data.get("line_items", []):
            modifiers = []
            for option in line_item.get("options", []):
                modifiers.append(option.get("name", ""))

            items.append(OrderItem(
                name=line_item.get("name", ""),
                quantity=line_item.get("quantity", 1),
                unit_price=line_item.get("price", 0) / 100,
                modifiers=modifiers,
                special_instructions=line_item.get("special_instructions", ""),
                external_id=line_item.get("id", ""),
            ))

        # Parse delivery info
        fulfillment = order_data.get("fulfillment", {})
        address = fulfillment.get("address", {})

        delivery = DeliveryInfo(
            type="delivery" if fulfillment.get("type") == "DELIVERY" else "pickup",
            address=f"{address.get('street_address', '')}, {address.get('city', '')}, {address.get('state', '')} {address.get('zip', '')}",
            latitude=address.get("latitude"),
            longitude=address.get("longitude"),
            instructions=fulfillment.get("instructions", ""),
        )

        # Parse pickup time
        pickup_time = fulfillment.get("pickup_time")
        if pickup_time:
            try:
                delivery.estimated_pickup_time = datetime.fromisoformat(
                    pickup_time.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        # Parse payment info
        payment = order_data.get("payment", {})
        subtotal = payment.get("subtotal", 0) / 100
        tax = payment.get("tax", 0) / 100
        tip = payment.get("tip", 0) / 100
        delivery_fee = payment.get("delivery_fee", 0) / 100
        total = payment.get("total", 0) / 100

        # Map Grubhub status to our status
        gh_status = order_data.get("status", "").upper()
        status_map = {
            "NEW": OrderStatus.PENDING,
            "RECEIVED": OrderStatus.PENDING,
            "CONFIRMED": OrderStatus.CONFIRMED,
            "IN_PROGRESS": OrderStatus.PREPARING,
            "READY": OrderStatus.READY,
            "PICKED_UP": OrderStatus.PICKED_UP,
            "DELIVERED": OrderStatus.DELIVERED,
            "CANCELLED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.CANCELLED,
        }
        status = status_map.get(gh_status, OrderStatus.PENDING)

        # Get customer info
        customer = order_data.get("customer", {})

        return NormalizedOrder(
            external_id=order_data.get("order_id", order_data.get("id", "")),
            platform=self.platform,
            customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            customer_phone=customer.get("phone", ""),
            customer_email=customer.get("email", ""),
            items=items,
            subtotal=subtotal,
            tax=tax,
            tip=tip,
            delivery_fee=delivery_fee,
            total=total,
            status=status,
            delivery=delivery,
            raw_payload=payload,
        )

    async def confirm_order(self, order: NormalizedOrder, prep_time_minutes: int = 15) -> bool:
        """
        Accept a Grubhub order.

        Must respond quickly or order may timeout.
        """
        if not order.external_id:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/orders/{order.external_id}/confirm",
                    headers=self._get_headers(),
                    json={
                        "prep_time_minutes": prep_time_minutes,
                    },
                )
                return response.status_code in [200, 204]
        except Exception:
            return False

    async def update_order_status(self, order: NormalizedOrder, status: OrderStatus) -> bool:
        """
        Update order status on Grubhub.
        """
        if not order.external_id:
            return False

        # Map our status to Grubhub actions
        status_map = {
            OrderStatus.PREPARING: "in_progress",
            OrderStatus.READY: "ready",
        }

        gh_status = status_map.get(status)
        if not gh_status:
            if status == OrderStatus.CANCELLED:
                return await self.cancel_order(order)
            return True

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/orders/{order.external_id}/status",
                    headers=self._get_headers(),
                    json={"status": gh_status},
                )
                return response.status_code in [200, 204]
        except Exception:
            return False

    async def cancel_order(self, order: NormalizedOrder, reason: str = "") -> bool:
        """Reject/cancel a Grubhub order."""
        if not order.external_id:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/orders/{order.external_id}/reject",
                    headers=self._get_headers(),
                    json={
                        "reason": reason or "Unable to fulfill order",
                        "reject_reason_code": "OTHER",
                    },
                )
                return response.status_code in [200, 204]
        except Exception:
            return False


# Singleton instance
grubhub_service = GrubhubService()
