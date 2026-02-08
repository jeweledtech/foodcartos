"""
Orders Router

Unified order management across all platforms:
- Square POS
- DoorDash
- UberEats
- Grubhub
- SMS pre-orders
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel

from app.services.supabase import order_service

router = APIRouter()


# ===========================================
# Models
# ===========================================


class OrderItem(BaseModel):
    """Individual item in an order."""
    name: str
    quantity: int
    unit_price: float
    modifiers: List[str] = []
    special_instructions: str = ""


class DeliveryInfo(BaseModel):
    """Delivery information."""
    type: str  # "delivery" or "pickup"
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    instructions: str = ""
    estimated_pickup_time: Optional[datetime] = None
    estimated_delivery_time: Optional[datetime] = None


class OrderCreate(BaseModel):
    """Create a new order."""
    org_id: str
    platform: str = "walk_in"
    external_id: Optional[str] = None
    cart_id: Optional[str] = None
    location_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    items: List[OrderItem]
    subtotal: float
    tax: float = 0
    tip: float = 0
    delivery_fee: float = 0
    total: float
    delivery: Optional[DeliveryInfo] = None


class OrderStatusUpdate(BaseModel):
    """Update order status."""
    status: str


class Order(BaseModel):
    """Order response model."""
    id: str
    org_id: str
    platform: str
    external_id: Optional[str] = None
    cart_id: Optional[str] = None
    location_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    items: List[dict]
    subtotal: float
    tax: float
    tip: float
    delivery_fee: float
    platform_fee: float
    total: float
    status: str
    delivery: Optional[dict] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class OrderStats(BaseModel):
    """Daily order statistics."""
    date: date
    total_orders: int
    total_revenue: float
    by_platform: dict
    by_status: dict


# ===========================================
# Endpoints
# ===========================================


@router.get("/", response_model=List[dict])
async def list_orders(
    org_id: str = Query(..., description="Organization ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    limit: int = Query(50, description="Max results"),
):
    """
    List orders for an organization.

    Filters:
    - status: pending, confirmed, preparing, ready, picked_up, delivered, cancelled
    - platform: square, doordash, ubereats, grubhub, sms, walk_in
    """
    orders = await order_service.list_by_org(
        org_id=org_id,
        status=status,
        platform=platform,
        limit=limit,
    )
    return orders


@router.get("/active", response_model=List[dict])
async def list_active_orders(
    org_id: str = Query(..., description="Organization ID"),
    cart_id: Optional[str] = Query(None, description="Filter by cart"),
):
    """
    List active orders (pending, confirmed, preparing, ready).

    This is what cart operators see on their display - the "ticket rail".
    """
    orders = await order_service.list_active(org_id=org_id, cart_id=cart_id)
    return orders


@router.get("/stats/daily", response_model=OrderStats)
async def get_daily_order_stats(
    org_id: str = Query(..., description="Organization ID"),
    date: date = Query(..., description="Date to get stats for"),
):
    """
    Get order statistics for a day.

    Shows breakdown by platform and status.
    """
    stats = await order_service.get_daily_order_stats(org_id, str(date))
    return OrderStats(
        date=date,
        total_orders=stats["total_orders"],
        total_revenue=stats["total_revenue"],
        by_platform=stats["by_platform"],
        by_status=stats["by_status"],
    )


@router.get("/{order_id}", response_model=dict)
async def get_order(order_id: str):
    """Get a specific order by ID."""
    order = await order_service.get_by_id(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return order


@router.post("/", response_model=dict)
async def create_order(order: OrderCreate):
    """
    Create a new order.

    This is typically called by webhook handlers or the SMS pre-order flow,
    but can also be used for walk-in orders created at the cart.
    """
    result = await order_service.create(
        org_id=order.org_id,
        platform=order.platform,
        external_id=order.external_id,
        cart_id=order.cart_id,
        location_id=order.location_id,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        customer_email=order.customer_email,
        items=[item.model_dump() for item in order.items],
        subtotal=order.subtotal,
        tax=order.tax,
        tip=order.tip,
        delivery_fee=order.delivery_fee,
        total=order.total,
        delivery=order.delivery.model_dump() if order.delivery else None,
    )
    return result


@router.patch("/{order_id}/status", response_model=dict)
async def update_order_status(order_id: str, update: OrderStatusUpdate):
    """
    Update order status.

    Valid transitions:
    - pending -> confirmed (accept order)
    - confirmed -> preparing (start cooking)
    - preparing -> ready (food is ready)
    - ready -> picked_up (driver/customer picked up)
    - picked_up -> delivered (delivery complete)
    - any -> cancelled (cancel order)
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    # Set timestamps based on status
    confirmed_at = now if update.status == "confirmed" else None
    ready_at = now if update.status == "ready" else None
    completed_at = now if update.status in ["delivered", "cancelled", "refunded"] else None

    result = await order_service.update_status(
        order_id=order_id,
        status=update.status,
        confirmed_at=confirmed_at,
        ready_at=ready_at,
        completed_at=completed_at,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return result


@router.post("/{order_id}/confirm", response_model=dict)
async def confirm_order(
    order_id: str,
    prep_time_minutes: int = Query(15, description="Estimated prep time"),
):
    """
    Confirm/accept an order.

    Sets status to 'confirmed' and calculates estimated ready time.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    result = await order_service.update_status(
        order_id=order_id,
        status="confirmed",
        confirmed_at=now,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    # TODO: Update platform (DoorDash, UberEats, etc.) with confirmation
    # TODO: Send SMS/push notification to customer

    return result


@router.post("/{order_id}/ready", response_model=dict)
async def mark_order_ready(order_id: str):
    """
    Mark an order as ready for pickup/delivery.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    result = await order_service.update_status(
        order_id=order_id,
        status="ready",
        ready_at=now,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    # TODO: Update platform with ready status
    # TODO: Send notification to customer/driver

    return result
