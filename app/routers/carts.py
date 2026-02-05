"""
Carts Router

Handles cart management, assignments, and real-time status.
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

router = APIRouter()


# ===========================================
# Models
# ===========================================


class CartBase(BaseModel):
    """Base cart fields."""

    name: str
    hardware_id: Optional[str] = None


class CartCreate(CartBase):
    """Create a new cart."""

    pass


class Cart(CartBase):
    """Cart with full details."""

    id: str
    org_id: str
    status: str  # active, inactive, maintenance
    current_location_id: Optional[str] = None
    current_location_name: Optional[str] = None
    last_seen: Optional[datetime] = None
    created_at: datetime


class CartAssignment(BaseModel):
    """Daily cart assignment."""

    id: str
    cart_id: str
    cart_name: str
    location_id: str
    location_name: str
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    date: date
    shift_start: Optional[str] = None  # "10:00"
    shift_end: Optional[str] = None  # "18:00"
    status: str  # scheduled, in_progress, completed, cancelled


class CartStatus(BaseModel):
    """Real-time cart status."""

    cart_id: str
    online: bool
    gps: Optional[dict] = None  # {"lat": 38.35, "lng": -121.98}
    last_transaction: Optional[datetime] = None
    today_revenue: float
    checklist_complete: bool
    signal_strength: Optional[int] = None


# ===========================================
# Endpoints
# ===========================================


@router.get("/", response_model=List[Cart])
async def list_carts(
    org_id: str = Query(..., description="Organization ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """
    List all carts for an organization.

    Returns basic cart information including current location.
    """
    # TODO: Implement with Supabase
    return [
        {
            "id": "cart_1",
            "org_id": org_id,
            "name": "Cart 1 - Main",
            "hardware_id": "pi_abc123",
            "status": "active",
            "current_location_id": "loc_1",
            "current_location_name": "Courthouse",
            "last_seen": datetime.now(),
            "created_at": datetime.now(),
        },
        {
            "id": "cart_2",
            "org_id": org_id,
            "name": "Cart 2 - Brother-in-law",
            "hardware_id": "pi_def456",
            "status": "active",
            "current_location_id": "loc_2",
            "current_location_name": "DMV",
            "last_seen": datetime.now(),
            "created_at": datetime.now(),
        },
    ]


@router.post("/", response_model=Cart, status_code=status.HTTP_201_CREATED)
async def create_cart(
    cart: CartCreate,
    org_id: str = Query(..., description="Organization ID"),
):
    """
    Create a new cart.

    Carts can be registered before hardware is installed.
    Hardware ID is added during physical setup.
    """
    # TODO: Implement with Supabase
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Cart creation not yet implemented",
    )


@router.get("/{cart_id}/status", response_model=CartStatus)
async def get_cart_status(cart_id: str):
    """
    Get real-time status for a cart.

    Returns:
    - Online/offline status
    - Current GPS location
    - Today's revenue
    - Checklist completion status
    - Signal strength (cellular)
    """
    # TODO: Implement with real data
    return {
        "cart_id": cart_id,
        "online": True,
        "gps": {"lat": 38.3566, "lng": -121.9877},
        "last_transaction": datetime.now(),
        "today_revenue": 347.00,
        "checklist_complete": True,
        "signal_strength": 18,
    }


@router.get("/assignments", response_model=List[CartAssignment])
async def list_assignments(
    org_id: str = Query(..., description="Organization ID"),
    date: date = Query(..., description="Assignment date"),
):
    """
    Get cart assignments for a specific date.

    Shows which cart goes to which location with which employee.
    """
    # TODO: Implement with Supabase
    return [
        {
            "id": "assign_1",
            "cart_id": "cart_1",
            "cart_name": "Cart 1 - Main",
            "location_id": "loc_1",
            "location_name": "Courthouse",
            "employee_id": "emp_poncho",
            "employee_name": "Poncho",
            "date": date,
            "shift_start": "10:00",
            "shift_end": "18:00",
            "status": "in_progress",
        },
        {
            "id": "assign_2",
            "cart_id": "cart_2",
            "cart_name": "Cart 2 - Brother-in-law",
            "location_id": "loc_2",
            "location_name": "DMV",
            "employee_id": "emp_brother",
            "employee_name": "Brother-in-law",
            "date": date,
            "shift_start": "10:30",
            "shift_end": "17:00",
            "status": "scheduled",
        },
    ]


@router.post("/assignments")
async def create_assignment(
    cart_id: str,
    location_id: str,
    date: date,
    employee_id: Optional[str] = None,
    shift_start: Optional[str] = None,
    shift_end: Optional[str] = None,
):
    """
    Create a cart assignment.

    Assigns a cart to a location for a specific date.
    Can include employee assignment and shift times.
    """
    # TODO: Implement with Supabase
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Assignment creation not yet implemented",
    )


@router.post("/{cart_id}/register")
async def register_cart_hardware(
    cart_id: str,
    hardware_id: str = Query(..., description="Raspberry Pi serial number"),
):
    """
    Register hardware with a cart.

    Called during physical cart setup when the Raspberry Pi
    is first connected and configured.
    """
    # TODO: Implement hardware registration
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Hardware registration not yet implemented",
    )
