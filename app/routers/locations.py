"""
Locations Router

Handles location management and intelligence features.
This is where the magic happens for Poncho's "which location is best" question.
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

router = APIRouter()


# ===========================================
# Models
# ===========================================


class LocationBase(BaseModel):
    """Base location fields."""

    name: str
    address: Optional[str] = None
    latitude: float
    longitude: float
    location_type: Optional[str] = None  # dmv, courthouse, event, etc.
    notes: Optional[str] = None


class LocationCreate(LocationBase):
    """Create a new location."""

    pass


class Location(LocationBase):
    """Location with ID and metadata."""

    id: str
    org_id: str
    created_at: datetime


class LocationPerformance(BaseModel):
    """Performance metrics for a location."""

    location_id: str
    location_name: str
    average_daily_revenue: float
    day_of_week_pattern: dict  # {0: 520, 1: 680, ...} (0=Monday)
    best_day: str
    best_day_revenue: float
    worst_day: str
    worst_day_revenue: float
    total_visits: int
    data_since: date


class LocationRecommendation(BaseModel):
    """Recommendation for a cart placement."""

    location_id: str
    location_name: str
    predicted_revenue: float
    confidence: str  # HIGH, MEDIUM, LOW
    reasons: List[str]


# ===========================================
# Endpoints
# ===========================================


@router.get("/", response_model=List[Location])
async def list_locations(
    org_id: str = Query(..., description="Organization ID"),
    location_type: Optional[str] = Query(None, description="Filter by type"),
):
    """
    List all locations for an organization.

    Optionally filter by location type (dmv, courthouse, event, etc.)
    """
    # TODO: Implement with Supabase
    # For now, return example data
    return [
        {
            "id": "loc_1",
            "org_id": org_id,
            "name": "Courthouse",
            "address": "123 Main St, Vacaville, CA",
            "latitude": 38.3566,
            "longitude": -121.9877,
            "location_type": "courthouse",
            "notes": "Jury duty days are Thursday - 74% higher revenue!",
            "created_at": datetime.now(),
        },
        {
            "id": "loc_2",
            "org_id": org_id,
            "name": "DMV",
            "address": "456 Oak Ave, Vacaville, CA",
            "latitude": 38.3600,
            "longitude": -121.9800,
            "location_type": "dmv",
            "notes": "Tuesdays are renewal day - best revenue",
            "created_at": datetime.now(),
        },
    ]


@router.post("/", response_model=Location, status_code=status.HTTP_201_CREATED)
async def create_location(
    location: LocationCreate,
    org_id: str = Query(..., description="Organization ID"),
):
    """
    Create a new location.

    Locations are specific spots where carts can operate.
    Track performance over time to build intelligence.
    """
    # TODO: Implement with Supabase
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Location creation not yet implemented",
    )


@router.get("/{location_id}/performance", response_model=LocationPerformance)
async def get_location_performance(location_id: str):
    """
    Get performance metrics for a location.

    This is what helps Poncho discover that Thursday courthouse
    makes 74% more than Wednesday courthouse.

    Returns:
    - Average daily revenue
    - Day-of-week patterns
    - Best and worst days
    - Total data points
    """
    # TODO: Implement with Supabase aggregation
    # Example response showing the courthouse pattern:
    return {
        "location_id": location_id,
        "location_name": "Courthouse",
        "average_daily_revenue": 680.00,
        "day_of_week_pattern": {
            "0": 520,  # Monday
            "1": 610,  # Tuesday
            "2": 510,  # Wednesday - Poncho was here
            "3": 890,  # Thursday - Jury duty! Should be here
            "4": 680,  # Friday
            "5": 0,  # Saturday - closed
            "6": 0,  # Sunday - closed
        },
        "best_day": "Thursday",
        "best_day_revenue": 890.00,
        "worst_day": "Wednesday",
        "worst_day_revenue": 510.00,
        "total_visits": 48,
        "data_since": date(2024, 1, 1),
    }


@router.get("/recommendations", response_model=List[LocationRecommendation])
async def get_recommendations(
    org_id: str = Query(..., description="Organization ID"),
    target_date: date = Query(..., description="Date to get recommendations for"),
    cart_ids: Optional[List[str]] = Query(None, description="Specific carts to place"),
):
    """
    Get location recommendations for a specific date.

    This is the core intelligence feature. Uses:
    - Historical revenue by location/day
    - Weather forecast
    - Local events
    - Cart count optimization

    Returns ranked recommendations with predicted revenue and confidence.
    """
    # TODO: Implement location scoring algorithm
    # Example response:
    day_of_week = target_date.strftime("%A")

    return [
        {
            "location_id": "loc_1",
            "location_name": "Courthouse",
            "predicted_revenue": 890.00,
            "confidence": "HIGH",
            "reasons": [
                f"{day_of_week} is jury duty day (+74% vs average)",
                "Weather forecast: Clear, 72°F",
                "No competing events nearby",
            ],
        },
        {
            "location_id": "loc_2",
            "location_name": "DMV",
            "predicted_revenue": 620.00,
            "confidence": "MEDIUM",
            "reasons": [
                f"{day_of_week} is average for this location",
                "Consider Tuesday for renewal day boost",
            ],
        },
        {
            "location_id": "loc_3",
            "location_name": "Downtown",
            "predicted_revenue": 480.00,
            "confidence": "MEDIUM",
            "reasons": [
                "Farmers market in area",
                "Morning traffic expected",
            ],
        },
    ]


@router.get("/{location_id}/compare")
async def compare_location(
    location_id: str,
    compare_to: List[str] = Query(..., description="Location IDs to compare"),
):
    """
    Compare performance between locations.

    Helps answer: "Should I move from DMV to Courthouse?"
    """
    # TODO: Implement comparison logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Location comparison not yet implemented",
    )
