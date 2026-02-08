"""
SMS Pre-Order Service

Allows customers to pre-order via SMS:
1. Customer texts "ORDER" to the cart's number
2. System sends back a simple menu
3. Customer replies with selection (e.g., "2 dirty dogs, 1 drink")
4. System confirms order and estimated pickup time

This is perfect for food cart regulars who know what they want.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from twilio.rest import Client as TwilioClient

from app.config import settings
from app.services.delivery_platforms.base import (
    DeliveryPlatform,
    DeliveryPlatformService,
    NormalizedOrder,
    OrderItem,
    OrderStatus,
    DeliveryInfo,
)


class SMSPreorderService(DeliveryPlatformService):
    """
    SMS-based pre-ordering for food carts.

    Flow:
    1. ORDER → Send menu
    2. Parse customer's text order (NLP-lite)
    3. Confirm order, provide pickup time
    4. Send ready notification

    This is incredibly powerful for food carts because:
    - No app download required
    - Works on any phone
    - Personal, direct connection with customers
    - Can build a loyal customer list
    """

    platform = DeliveryPlatform.SMS

    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.phone_number = settings.TWILIO_PHONE_NUMBER
        self.messaging_service_sid = settings.TWILIO_MESSAGING_SERVICE_SID

        self._client: Optional[TwilioClient] = None

    @property
    def client(self) -> TwilioClient:
        """Lazy-load Twilio client."""
        if self._client is None and self.account_sid and self.auth_token:
            self._client = TwilioClient(self.account_sid, self.auth_token)
        return self._client

    def verify_webhook(self, payload: bytes, signature: str, **kwargs) -> bool:
        """
        Verify Twilio webhook signature.

        Twilio uses a different verification method - comparing
        the signature to a hash of the URL + params.
        """
        from twilio.request_validator import RequestValidator

        if not self.auth_token:
            return False

        url = kwargs.get("url", "")
        params = kwargs.get("params", {})

        validator = RequestValidator(self.auth_token)
        return validator.validate(url, params, signature)

    def parse_order(self, payload: dict) -> NormalizedOrder:
        """
        Parse SMS message into an order.

        This uses simple pattern matching to extract items.
        Examples it understands:
        - "2 dirty dogs"
        - "1 brisket, 2 drinks"
        - "3 hot dogs with everything, 1 large drink"
        """
        message_body = payload.get("Body", "").strip()
        from_number = payload.get("From", "")

        items = self._parse_items_from_text(message_body)

        # Calculate totals (using placeholder prices)
        subtotal = sum(item.total_price for item in items)
        tax = round(subtotal * 0.0875, 2)  # ~8.75% CA tax
        total = subtotal + tax

        # Pickup order by default
        delivery = DeliveryInfo(
            type="pickup",
            estimated_pickup_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        )

        return NormalizedOrder(
            external_id=payload.get("MessageSid", ""),
            platform=self.platform,
            customer_phone=from_number,
            items=items,
            subtotal=subtotal,
            tax=tax,
            total=total,
            status=OrderStatus.PENDING,
            delivery=delivery,
            raw_payload=payload,
        )

    def _parse_items_from_text(self, text: str) -> list[OrderItem]:
        """
        Parse natural language text into order items.

        This is intentionally simple and forgiving.
        """
        items = []

        # Normalize text
        text = text.lower().strip()

        # Common item patterns for hot dog carts
        # These would ideally be loaded from the cart's menu
        menu_patterns = {
            r"(\d+)?\s*dirty\s*(?:water\s*)?dogs?": ("Dirty Water Dog", 10.00),
            r"(\d+)?\s*brisket\s*dogs?": ("Brisket Dog", 12.00),
            r"(\d+)?\s*classic\s*dogs?": ("Classic Dog", 8.00),
            r"(\d+)?\s*hot\s*dogs?": ("Classic Dog", 8.00),
            r"(\d+)?\s*dogs?": ("Classic Dog", 8.00),
            r"(\d+)?\s*(?:large\s*)?drinks?": ("Drink", 3.00),
            r"(\d+)?\s*sodas?": ("Drink", 3.00),
            r"(\d+)?\s*waters?": ("Water", 2.00),
            r"(\d+)?\s*chips": ("Chips", 2.50),
        }

        for pattern, (item_name, price) in menu_patterns.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                quantity = int(match.group(1)) if match.group(1) else 1
                items.append(OrderItem(
                    name=item_name,
                    quantity=quantity,
                    unit_price=price,
                ))
                # Remove matched text to avoid double-counting
                text = text[:match.start()] + " " + text[match.end():]

        # If no items parsed, treat the whole message as a custom order
        if not items and len(text.strip()) > 2:
            items.append(OrderItem(
                name="Custom Order",
                quantity=1,
                unit_price=0.00,
                special_instructions=text.strip(),
            ))

        return items

    async def confirm_order(self, order: NormalizedOrder, prep_time_minutes: int = 15) -> bool:
        """
        Confirm SMS order by sending confirmation message.
        """
        if not order.customer_phone or not self.client:
            return False

        pickup_time = datetime.now(timezone.utc) + timedelta(minutes=prep_time_minutes)

        # Build items list
        items_text = "\n".join([
            f"  • {item.quantity}x {item.name} - ${item.total_price:.2f}"
            for item in order.items
        ])

        message = f"""✅ Order confirmed!

{items_text}

Total: ${order.total:.2f}

Ready for pickup at: {pickup_time.strftime('%I:%M %p')}

Reply CANCEL to cancel your order.
"""

        return await self._send_sms(order.customer_phone, message)

    async def update_order_status(self, order: NormalizedOrder, status: OrderStatus) -> bool:
        """
        Send SMS notification for status updates.
        """
        if not order.customer_phone or not self.client:
            return False

        messages = {
            OrderStatus.PREPARING: "🍳 Your order is being prepared!",
            OrderStatus.READY: "🔔 Your order is READY for pickup! See you soon!",
            OrderStatus.CANCELLED: "❌ Your order has been cancelled. Reply ORDER to start a new one.",
        }

        message = messages.get(status)
        if message:
            return await self._send_sms(order.customer_phone, message)

        return True

    async def cancel_order(self, order: NormalizedOrder, reason: str = "") -> bool:
        """Cancel SMS order and notify customer."""
        message = "❌ Your order has been cancelled."
        if reason:
            message += f"\n\nReason: {reason}"
        message += "\n\nReply ORDER to place a new order."

        return await self._send_sms(order.customer_phone, message)

    async def _send_sms(self, to_number: str, message: str) -> bool:
        """Send an SMS message via Twilio."""
        if not self.client:
            return False

        try:
            if self.messaging_service_sid:
                self.client.messages.create(
                    body=message,
                    messaging_service_sid=self.messaging_service_sid,
                    to=to_number,
                )
            else:
                self.client.messages.create(
                    body=message,
                    from_=self.phone_number,
                    to=to_number,
                )
            return True
        except Exception:
            return False

    async def send_menu(self, to_number: str, cart_name: str = "Food Cart") -> bool:
        """
        Send the menu when customer texts ORDER.

        This should be customized per cart.
        """
        menu = f"""🌭 {cart_name} Menu

DOGS:
• Dirty Water Dog - $10
• Brisket Dog - $12
• Classic Dog - $8

DRINKS:
• Soda - $3
• Water - $2

SIDES:
• Chips - $2.50

Reply with your order!
Example: "2 dirty dogs, 1 soda"
"""
        return await self._send_sms(to_number, menu)

    async def handle_incoming_sms(self, from_number: str, body: str, org_id: str) -> dict:
        """
        Handle incoming SMS and determine action.

        Returns action type and any relevant data.
        """
        body_upper = body.strip().upper()

        if body_upper == "ORDER" or body_upper.startswith("ORDER"):
            # Send menu
            await self.send_menu(from_number)
            return {"action": "menu_sent", "from": from_number}

        elif body_upper == "CANCEL":
            # Cancel pending order
            return {"action": "cancel_requested", "from": from_number}

        elif body_upper == "HELP":
            help_text = "Text ORDER to see menu.\nText STOP to unsubscribe."
            await self._send_sms(from_number, help_text)
            return {"action": "help_sent", "from": from_number}

        elif body_upper == "STOP":
            # Twilio handles unsubscribe, but we should track it
            return {"action": "unsubscribed", "from": from_number}

        else:
            # Try to parse as an order
            order = self.parse_order({
                "Body": body,
                "From": from_number,
            })
            order.org_id = org_id

            if order.items:
                return {
                    "action": "order_received",
                    "order": order,
                    "from": from_number,
                }
            else:
                # Couldn't parse, ask for clarification
                await self._send_sms(
                    from_number,
                    "Sorry, I didn't understand that. Text ORDER to see the menu."
                )
                return {"action": "unknown", "from": from_number, "body": body}


# Singleton instance
sms_preorder_service = SMSPreorderService()
