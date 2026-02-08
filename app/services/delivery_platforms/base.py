"""
Delivery Platform Base Service

Provides a unified interface for all delivery platform integrations.
Each platform (DoorDash, UberEats, Grubhub, SMS) extends this base class.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import hashlib
import hmac


class DeliveryPlatform(str, Enum):
    """Supported delivery platforms."""
    SQUARE = "square"
    DOORDASH = "doordash"
    UBEREATS = "ubereats"
    GRUBHUB = "grubhub"
    SMS = "sms"
    WALK_IN = "walk_in"


class OrderStatus(str, Enum):
    """Unified order status across all platforms."""
    PENDING = "pending"           # Order received, not yet confirmed
    CONFIRMED = "confirmed"       # Order accepted by cart
    PREPARING = "preparing"       # Being prepared
    READY = "ready"              # Ready for pickup/delivery
    PICKED_UP = "picked_up"      # Driver picked up (delivery) or customer picked up
    DELIVERED = "delivered"      # Delivered to customer
    CANCELLED = "cancelled"      # Order cancelled
    REFUNDED = "refunded"        # Order refunded


@dataclass
class OrderItem:
    """Individual item in an order."""
    name: str
    quantity: int
    unit_price: float
    modifiers: list[str] = field(default_factory=list)
    special_instructions: str = ""
    external_id: str = ""  # Platform-specific item ID

    @property
    def total_price(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class DeliveryInfo:
    """Delivery information (if applicable)."""
    type: str  # "delivery" or "pickup"
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    instructions: str = ""
    estimated_pickup_time: Optional[datetime] = None
    estimated_delivery_time: Optional[datetime] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None


@dataclass
class NormalizedOrder:
    """
    Unified order format that works across all platforms.

    This is what gets stored in our database regardless of source.
    """
    # Core identifiers
    id: Optional[str] = None  # Our internal ID (set after DB insert)
    external_id: str = ""     # Platform's order ID
    platform: DeliveryPlatform = DeliveryPlatform.WALK_IN

    # Organization context
    org_id: str = ""
    cart_id: Optional[str] = None
    location_id: Optional[str] = None

    # Customer info
    customer_name: str = ""
    customer_phone: str = ""
    customer_email: str = ""

    # Order details
    items: list[OrderItem] = field(default_factory=list)
    subtotal: float = 0.0
    tax: float = 0.0
    tip: float = 0.0
    delivery_fee: float = 0.0
    platform_fee: float = 0.0  # What the platform charges
    total: float = 0.0

    # Status tracking
    status: OrderStatus = OrderStatus.PENDING

    # Delivery info
    delivery: Optional[DeliveryInfo] = None

    # Timestamps
    created_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Raw data for debugging
    raw_payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "external_id": self.external_id,
            "platform": self.platform.value,
            "org_id": self.org_id,
            "cart_id": self.cart_id,
            "location_id": self.location_id,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "customer_email": self.customer_email,
            "items": [
                {
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "modifiers": item.modifiers,
                    "special_instructions": item.special_instructions,
                    "external_id": item.external_id,
                }
                for item in self.items
            ],
            "subtotal": self.subtotal,
            "tax": self.tax,
            "tip": self.tip,
            "delivery_fee": self.delivery_fee,
            "platform_fee": self.platform_fee,
            "total": self.total,
            "status": self.status.value,
            "delivery": {
                "type": self.delivery.type,
                "address": self.delivery.address,
                "latitude": self.delivery.latitude,
                "longitude": self.delivery.longitude,
                "instructions": self.delivery.instructions,
                "estimated_pickup_time": self.delivery.estimated_pickup_time.isoformat() if self.delivery.estimated_pickup_time else None,
                "estimated_delivery_time": self.delivery.estimated_delivery_time.isoformat() if self.delivery.estimated_delivery_time else None,
            } if self.delivery else None,
            "raw_payload": self.raw_payload,
        }


class DeliveryPlatformService(ABC):
    """
    Abstract base class for delivery platform integrations.

    Each platform (DoorDash, UberEats, Grubhub) implements this interface.
    """

    platform: DeliveryPlatform

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str, **kwargs) -> bool:
        """
        Verify webhook signature from the platform.

        Each platform uses different signing methods.
        """
        pass

    @abstractmethod
    def parse_order(self, payload: dict) -> NormalizedOrder:
        """
        Parse platform-specific order payload into NormalizedOrder.

        This is where we translate platform-specific formats.
        """
        pass

    @abstractmethod
    async def confirm_order(self, order: NormalizedOrder, prep_time_minutes: int = 15) -> bool:
        """
        Confirm/accept an order with the platform.

        Returns True if successful.
        """
        pass

    @abstractmethod
    async def update_order_status(self, order: NormalizedOrder, status: OrderStatus) -> bool:
        """
        Update order status on the platform.

        Not all platforms support all statuses.
        """
        pass

    @abstractmethod
    async def cancel_order(self, order: NormalizedOrder, reason: str = "") -> bool:
        """
        Cancel an order on the platform.
        """
        pass

    def _hmac_verify(self, payload: bytes, signature: str, secret: str, algorithm: str = "sha256") -> bool:
        """
        Helper for HMAC-based signature verification.

        Many platforms use HMAC-SHA256.
        """
        if algorithm == "sha256":
            expected = hmac.new(
                secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
        elif algorithm == "sha1":
            expected = hmac.new(
                secret.encode(),
                payload,
                hashlib.sha1
            ).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        return hmac.compare_digest(expected, signature)
