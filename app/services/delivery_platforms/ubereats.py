"""
UberEats Integration Service

Handles Uber Eats Marketplace integration for receiving orders.

API Docs: https://developer.uber.com/docs/eats/introduction
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


class UberEatsService(DeliveryPlatformService):
    """
    UberEats integration for FoodCartOS.

    Handles:
    - OAuth2 authentication
    - Webhook verification
    - Order parsing from UberEats format
    - Order status updates
    - Menu sync (future)
    """

    platform = DeliveryPlatform.UBEREATS

    # API endpoints
    SANDBOX_URL = "https://api.uber.com/v1/eats"
    PRODUCTION_URL = "https://api.uber.com/v1/eats"
    AUTH_URL = "https://auth.uber.com/oauth/v2/token"

    def __init__(self):
        self.client_id = settings.UBEREATS_CLIENT_ID
        self.client_secret = settings.UBEREATS_CLIENT_SECRET
        self.webhook_secret = settings.UBEREATS_WEBHOOK_SECRET
        self.environment = settings.UBEREATS_ENVIRONMENT

        self.base_url = self.PRODUCTION_URL if self.environment == "production" else self.SANDBOX_URL
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

    async def _get_access_token(self) -> str:
        """
        Get OAuth2 access token for UberEats API.

        Uses client credentials flow.
        """
        import time

        # Return cached token if still valid
        if self._access_token and self._token_expires_at:
            if time.time() < self._token_expires_at - 60:  # 1 min buffer
                return self._access_token

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.AUTH_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                    "scope": "eats.order eats.store",
                },
            )

            if response.status_code == 200:
                data = response.json()
                self._access_token = data["access_token"]
                self._token_expires_at = time.time() + data.get("expires_in", 3600)
                return self._access_token

            raise Exception(f"Failed to get UberEats token: {response.text}")

    async def _get_headers(self) -> dict:
        """Get headers for UberEats API requests."""
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def verify_webhook(self, payload: bytes, signature: str, **kwargs) -> bool:
        """
        Verify UberEats webhook signature.

        UberEats uses HMAC-SHA256 for webhook verification.
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
        Parse UberEats order webhook into NormalizedOrder.

        UberEats sends orders via webhook with detailed item info.
        """
        # Handle different webhook event types
        event_type = payload.get("event_type", "")
        order_data = payload.get("order", payload.get("meta", {}).get("resource", payload))

        # Parse items
        items = []
        for cart_item in order_data.get("cart", {}).get("items", []):
            modifiers = []
            for selected in cart_item.get("selected_modifier_groups", []):
                for mod in selected.get("selected_items", []):
                    modifiers.append(mod.get("title", ""))

            items.append(OrderItem(
                name=cart_item.get("title", ""),
                quantity=cart_item.get("quantity", 1),
                unit_price=cart_item.get("price", {}).get("unit_price", {}).get("amount", 0) / 100,
                modifiers=modifiers,
                special_instructions=cart_item.get("special_instructions", ""),
                external_id=cart_item.get("id", ""),
            ))

        # Parse delivery info
        eater = order_data.get("eater", {})
        delivery_info = order_data.get("delivery_info", {})

        delivery = DeliveryInfo(
            type="delivery" if order_data.get("type") == "DELIVERY" else "pickup",
            address=delivery_info.get("location", {}).get("formatted_address", ""),
            latitude=delivery_info.get("location", {}).get("latitude"),
            longitude=delivery_info.get("location", {}).get("longitude"),
            instructions=delivery_info.get("notes", ""),
        )

        # Parse estimated times
        estimated_ready = order_data.get("estimated_ready_for_pickup_at")
        if estimated_ready:
            try:
                delivery.estimated_pickup_time = datetime.fromisoformat(
                    estimated_ready.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        # Parse payment info
        payment = order_data.get("payment", {})
        charges = payment.get("charges", {})

        subtotal = charges.get("sub_total", {}).get("amount", 0) / 100
        tax = charges.get("tax", {}).get("amount", 0) / 100
        tip = charges.get("tips", {}).get("amount", 0) / 100
        delivery_fee = charges.get("delivery_fee", {}).get("amount", 0) / 100
        total = charges.get("total", {}).get("amount", 0) / 100

        # Map UberEats status to our status
        ue_status = order_data.get("current_state", "").upper()
        status_map = {
            "CREATED": OrderStatus.PENDING,
            "ACCEPTED": OrderStatus.CONFIRMED,
            "DENIED": OrderStatus.CANCELLED,
            "IN_PROGRESS": OrderStatus.PREPARING,
            "READY_FOR_PICKUP": OrderStatus.READY,
            "PICKED_UP": OrderStatus.PICKED_UP,
            "DELIVERED": OrderStatus.DELIVERED,
            "CANCELLED": OrderStatus.CANCELLED,
        }
        status = status_map.get(ue_status, OrderStatus.PENDING)

        return NormalizedOrder(
            external_id=order_data.get("id", ""),
            platform=self.platform,
            customer_name=f"{eater.get('first_name', '')} {eater.get('last_name', '')}".strip(),
            customer_phone=eater.get("phone", ""),
            customer_email=eater.get("email", ""),
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
        Accept an UberEats order.

        Must respond within 10 minutes or order auto-cancels.
        """
        if not order.external_id:
            return False

        try:
            headers = await self._get_headers()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/orders/{order.external_id}/accept_pos_order",
                    headers=headers,
                    json={
                        "reason": "Order accepted",
                        "estimated_prep_time": prep_time_minutes,
                    },
                )
                return response.status_code in [200, 204]
        except Exception:
            return False

    async def update_order_status(self, order: NormalizedOrder, status: OrderStatus) -> bool:
        """
        Update order status on UberEats.

        UberEats supports specific status transitions.
        """
        if not order.external_id:
            return False

        # Map our status to UberEats actions
        action_map = {
            OrderStatus.PREPARING: "start_preparing",
            OrderStatus.READY: "ready_for_pickup",
        }

        action = action_map.get(status)
        if not action:
            if status == OrderStatus.CANCELLED:
                return await self.cancel_order(order)
            return True  # Status not supported, but not an error

        try:
            headers = await self._get_headers()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/orders/{order.external_id}/{action}",
                    headers=headers,
                )
                return response.status_code in [200, 204]
        except Exception:
            return False

    async def cancel_order(self, order: NormalizedOrder, reason: str = "") -> bool:
        """Cancel an UberEats order."""
        if not order.external_id:
            return False

        # UberEats cancel reasons
        cancel_reasons = [
            "ITEM_AVAILABILITY",
            "STORE_CLOSED",
            "CANNOT_COMPLETE",
            "OTHER",
        ]

        try:
            headers = await self._get_headers()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/orders/{order.external_id}/deny_pos_order",
                    headers=headers,
                    json={
                        "reason": {
                            "explanation": reason or "Unable to fulfill order",
                            "code": "CANNOT_COMPLETE",
                        },
                    },
                )
                return response.status_code in [200, 204]
        except Exception:
            return False

    async def get_store_status(self, store_id: str) -> Optional[dict]:
        """Get store status (open/closed, paused, etc.)."""
        try:
            headers = await self._get_headers()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/stores/{store_id}",
                    headers=headers,
                )

                if response.status_code == 200:
                    return response.json()
                return None
        except Exception:
            return None

    async def pause_store(self, store_id: str, pause_reason: str = "temporary_pause") -> bool:
        """Temporarily pause receiving orders."""
        try:
            headers = await self._get_headers()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/stores/{store_id}/status",
                    headers=headers,
                    json={
                        "status": "PAUSED",
                        "reason": pause_reason,
                    },
                )
                return response.status_code in [200, 204]
        except Exception:
            return False


# Singleton instance
ubereats_service = UberEatsService()
