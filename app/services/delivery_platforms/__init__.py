"""
Delivery Platform Integrations

Unified interface for receiving orders from multiple delivery platforms:
- DoorDash
- UberEats
- Grubhub
- SMS Pre-orders (via Twilio)
"""

from app.services.delivery_platforms.base import (
    DeliveryPlatform,
    DeliveryPlatformService,
    NormalizedOrder,
    OrderItem,
    OrderStatus,
    DeliveryInfo,
)
from app.services.delivery_platforms.doordash import doordash_service, DoorDashService
from app.services.delivery_platforms.ubereats import ubereats_service, UberEatsService
from app.services.delivery_platforms.grubhub import grubhub_service, GrubhubService
from app.services.delivery_platforms.sms_preorder import sms_preorder_service, SMSPreorderService

__all__ = [
    # Base classes
    "DeliveryPlatform",
    "DeliveryPlatformService",
    "NormalizedOrder",
    "OrderItem",
    "OrderStatus",
    "DeliveryInfo",
    # Platform services
    "doordash_service",
    "DoorDashService",
    "ubereats_service",
    "UberEatsService",
    "grubhub_service",
    "GrubhubService",
    "sms_preorder_service",
    "SMSPreorderService",
]
