"""
DoorDash Integration Service

Supports both:
- DoorDash Drive API (use DoorDash drivers for your orders)
- DoorDash Marketplace Webhooks (receive orders from DoorDash app)

API Docs: https://developer.doordash.com/
"""

import json
import jwt
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

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


class DoorDashService(DeliveryPlatformService):
    """
    DoorDash integration for FoodCartOS.

    Handles:
    - Webhook verification
    - Order parsing from DoorDash format
    - Order status updates
    - DoorDash Drive delivery creation
    """

    platform = DeliveryPlatform.DOORDASH

    # API endpoints
    SANDBOX_URL = "https://openapi.doordash.com/drive/v2"
    PRODUCTION_URL = "https://openapi.doordash.com/drive/v2"

    def __init__(self):
        self.developer_id = settings.DOORDASH_DEVELOPER_ID
        self.key_id = settings.DOORDASH_KEY_ID
        self.signing_secret = settings.DOORDASH_SIGNING_SECRET
        self.environment = settings.DOORDASH_ENVIRONMENT

        self.base_url = self.PRODUCTION_URL if self.environment == "production" else self.SANDBOX_URL

    def _create_jwt(self) -> str:
        """
        Create a JWT for DoorDash API authentication.

        DoorDash uses JWT tokens signed with your signing secret.
        """
        payload = {
            "aud": "doordash",
            "iss": self.developer_id,
            "kid": self.key_id,
            "exp": int(time.time()) + 300,  # 5 minutes
            "iat": int(time.time()),
        }

        return jwt.encode(
            payload,
            self.signing_secret,
            algorithm="HS256",
            headers={"dd-ver": "DD-JWT-V1"},
        )

    def _get_headers(self) -> dict:
        """Get headers for DoorDash API requests."""
        return {
            "Authorization": f"Bearer {self._create_jwt()}",
            "Content-Type": "application/json",
        }

    def verify_webhook(self, payload: bytes, signature: str, **kwargs) -> bool:
        """
        Verify DoorDash webhook signature.

        DoorDash signs webhooks with HMAC-SHA256.
        """
        if not self.signing_secret:
            return False

        return self._hmac_verify(
            payload=payload,
            signature=signature,
            secret=self.signing_secret,
            algorithm="sha256",
        )

    def parse_order(self, payload: dict) -> NormalizedOrder:
        """
        Parse DoorDash order webhook into NormalizedOrder.

        DoorDash webhook payload structure varies by event type.
        """
        # Extract order data
        order_data = payload.get("order", payload)

        # Parse items
        items = []
        for item in order_data.get("order_items", []):
            items.append(OrderItem(
                name=item.get("name", ""),
                quantity=item.get("quantity", 1),
                unit_price=item.get("unit_price", 0) / 100,  # Convert cents
                modifiers=[m.get("name", "") for m in item.get("modifiers", [])],
                special_instructions=item.get("special_instructions", ""),
                external_id=item.get("id", ""),
            ))

        # Parse delivery info
        dropoff = order_data.get("dropoff_address", {})
        delivery = DeliveryInfo(
            type="delivery",
            address=dropoff.get("full_address", ""),
            latitude=dropoff.get("lat"),
            longitude=dropoff.get("lng"),
            instructions=order_data.get("dropoff_instructions", ""),
        )

        # Parse pickup time if available
        pickup_time = order_data.get("pickup_time")
        if pickup_time:
            try:
                delivery.estimated_pickup_time = datetime.fromisoformat(
                    pickup_time.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        # Calculate totals
        subtotal = order_data.get("order_value", 0) / 100
        tip = order_data.get("tip", 0) / 100
        delivery_fee = order_data.get("delivery_fee", 0) / 100
        total = subtotal + tip + delivery_fee

        # Map DoorDash status to our status
        dd_status = order_data.get("status", "").lower()
        status_map = {
            "created": OrderStatus.PENDING,
            "confirmed": OrderStatus.CONFIRMED,
            "pickup_in_progress": OrderStatus.PREPARING,
            "picked_up": OrderStatus.PICKED_UP,
            "delivered": OrderStatus.DELIVERED,
            "cancelled": OrderStatus.CANCELLED,
        }
        status = status_map.get(dd_status, OrderStatus.PENDING)

        # Get customer info
        customer = order_data.get("customer", {})

        return NormalizedOrder(
            external_id=order_data.get("external_delivery_id", order_data.get("id", "")),
            platform=self.platform,
            customer_name=customer.get("name", "DoorDash Customer"),
            customer_phone=customer.get("phone_number", ""),
            customer_email=customer.get("email", ""),
            items=items,
            subtotal=subtotal,
            tip=tip,
            delivery_fee=delivery_fee,
            total=total,
            status=status,
            delivery=delivery,
            raw_payload=payload,
        )

    async def confirm_order(self, order: NormalizedOrder, prep_time_minutes: int = 15) -> bool:
        """
        Confirm order with DoorDash.

        For Drive orders, this updates the pickup time.
        """
        if not order.external_id:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/deliveries/{order.external_id}",
                    headers=self._get_headers(),
                    json={
                        "pickup_time": (
                            datetime.now(timezone.utc).isoformat()
                            if prep_time_minutes == 0
                            else None
                        ),
                    },
                )
                return response.status_code in [200, 204]
        except Exception:
            return False

    async def update_order_status(self, order: NormalizedOrder, status: OrderStatus) -> bool:
        """
        Update order status on DoorDash.

        DoorDash Drive has limited status updates - mainly for cancellation.
        """
        if status == OrderStatus.CANCELLED:
            return await self.cancel_order(order)

        # For "ready" status, we could trigger driver dispatch
        # but DoorDash typically handles this automatically
        return True

    async def cancel_order(self, order: NormalizedOrder, reason: str = "") -> bool:
        """Cancel a DoorDash Drive delivery."""
        if not order.external_id:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/deliveries/{order.external_id}/cancel",
                    headers=self._get_headers(),
                )
                return response.status_code in [200, 204]
        except Exception:
            return False

    # =========================================
    # DoorDash Drive - Create Delivery
    # =========================================

    async def create_drive_delivery(
        self,
        pickup_address: dict,
        dropoff_address: dict,
        order_value: int,  # in cents
        items: list[dict],
        customer_name: str = "",
        customer_phone: str = "",
        pickup_instructions: str = "",
        dropoff_instructions: str = "",
        tip: int = 0,  # in cents
    ) -> Optional[dict]:
        """
        Create a DoorDash Drive delivery.

        This lets you use DoorDash drivers for orders you receive
        from other channels (phone, SMS, walk-in, etc.).

        Args:
            pickup_address: {"street": "123 Main St", "city": "...", ...}
            dropoff_address: {"street": "456 Oak Ave", "city": "...", ...}
            order_value: Total order value in cents
            items: List of item dicts with name, quantity, price
            customer_name: Customer's name
            customer_phone: Customer's phone number
            pickup_instructions: Instructions for driver at pickup
            dropoff_instructions: Instructions for driver at dropoff
            tip: Tip amount in cents

        Returns:
            DoorDash delivery response or None on error
        """
        import uuid

        external_delivery_id = str(uuid.uuid4())

        payload = {
            "external_delivery_id": external_delivery_id,
            "pickup_address": self._format_address(pickup_address),
            "pickup_business_name": pickup_address.get("business_name", "Food Cart"),
            "pickup_phone_number": pickup_address.get("phone", ""),
            "pickup_instructions": pickup_instructions,
            "dropoff_address": self._format_address(dropoff_address),
            "dropoff_phone_number": customer_phone,
            "dropoff_instructions": dropoff_instructions,
            "customer": {
                "first_name": customer_name.split()[0] if customer_name else "Customer",
                "last_name": customer_name.split()[-1] if customer_name and len(customer_name.split()) > 1 else "",
                "phone_number": customer_phone,
            },
            "order_value": order_value,
            "items": [
                {
                    "name": item.get("name", "Item"),
                    "quantity": item.get("quantity", 1),
                    "price": item.get("price", 0),
                }
                for item in items
            ],
            "tip": tip,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/deliveries",
                    headers=self._get_headers(),
                    json=payload,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": response.text, "status_code": response.status_code}
        except Exception as e:
            return {"error": str(e)}

    def _format_address(self, address: dict) -> str:
        """Format address dict into string for DoorDash API."""
        parts = []
        if address.get("street"):
            parts.append(address["street"])
        if address.get("city"):
            parts.append(address["city"])
        if address.get("state"):
            parts.append(address["state"])
        if address.get("zip"):
            parts.append(address["zip"])

        return ", ".join(parts) if parts else address.get("full_address", "")

    async def get_delivery_status(self, external_delivery_id: str) -> Optional[dict]:
        """Get the current status of a DoorDash Drive delivery."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/deliveries/{external_delivery_id}",
                    headers=self._get_headers(),
                )

                if response.status_code == 200:
                    return response.json()
                return None
        except Exception:
            return None


# Singleton instance
doordash_service = DoorDashService()
