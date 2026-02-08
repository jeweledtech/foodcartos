"""
Locations Router

Handles location management and intelligence features.
This is where the magic happens for Poncho's "which location is best" question.
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.services.supabase import location_service, transaction_service

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
    location_type: Optional[str] = None
    notes: Optional[str] = None


class LocationCreate(LocationBase):
    """Create a new location."""

    pass


class Location(LocationBase):
    """Location with ID and metadata."""

    id: str
    org_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class LocationPerformance(BaseModel):
    """Performance metrics for a location."""

    location_id: str
    location_name: str
    average_daily_revenue: float
    day_of_week_pattern: dict
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
    confidence: str
    reasons: List[str]


# ===========================================
# Endpoints
# ===========================================


@router.get("/", response_model=List[dict])
async def list_locations(
    org_id: str = Query(..., description="Organization ID"),
    location_type: Optional[str] = Query(None, description="Filter by type"),
):
    """
    List all locations for an organization.

    Optionally filter by location type (dmv, courthouse, event, etc.)
    """
    locations = await location_service.list_by_org(org_id, location_type)
    return locations


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_location(
    location: LocationCreate,
    org_id: str = Query(..., description="Organization ID"),
):
    """
    Create a new location.

    Locations are specific spots where carts can operate.
    Track performance over time to build intelligence.
    """
    result = await location_service.create(
        org_id=org_id,
        name=location.name,
        latitude=location.latitude,
        longitude=location.longitude,
        address=location.address,
        location_type=location.location_type,
        notes=location.notes,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create location",
        )

    return result


@router.get("/{location_id}", response_model=dict)
async def get_location(location_id: str):
    """Get a single location by ID."""
    location = await location_service.get_by_id(location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )
    return location


@router.get("/{location_id}/performance", response_model=LocationPerformance)
async def get_location_performance(
    location_id: str,
    days: int = Query(30, description="Number of days to analyze"),
):
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
    location = await location_service.get_by_id(location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )

    # Get transactions for this location
    end_date = datetime.now()
    start_date = end_date - __import__("datetime").timedelta(days=days)

    transactions = await transaction_service.list_by_date_range(
        org_id=location["org_id"],
        start_date=start_date.isoformat() + "Z",
        end_date=end_date.isoformat() + "Z",
        location_id=location_id,
    )

    # Calculate day-of-week patterns
    # day_of_week: 0=Sunday, 1=Monday, ..., 6=Saturday
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    day_totals = {i: 0.0 for i in range(7)}
    day_counts = {i: 0 for i in range(7)}

    for t in transactions:
        dow = t.get("day_of_week", 0)
        day_totals[dow] += t["amount"]
        day_counts[dow] += 1

    # Calculate averages
    day_averages = {}
    for i in range(7):
        if day_counts[i] > 0:
            day_averages[str(i)] = round(day_totals[i] / day_counts[i], 2)
        else:
            day_averages[str(i)] = 0

    # Find best and worst days
    non_zero_days = {k: v for k, v in day_averages.items() if v > 0}
    if non_zero_days:
        best_day_num = max(non_zero_days, key=non_zero_days.get)
        worst_day_num = min(non_zero_days, key=non_zero_days.get)
        best_day = day_names[int(best_day_num)]
        worst_day = day_names[int(worst_day_num)]
        best_revenue = non_zero_days[best_day_num]
        worst_revenue = non_zero_days[worst_day_num]
    else:
        best_day = "N/A"
        worst_day = "N/A"
        best_revenue = 0
        worst_revenue = 0

    # Calculate overall average
    total_revenue = sum(t["amount"] for t in transactions)
    unique_days = len(set(t["timestamp"][:10] for t in transactions))
    avg_daily = total_revenue / unique_days if unique_days > 0 else 0

    return LocationPerformance(
        location_id=location_id,
        location_name=location["name"],
        average_daily_revenue=round(avg_daily, 2),
        day_of_week_pattern=day_averages,
        best_day=best_day,
        best_day_revenue=best_revenue,
        worst_day=worst_day,
        worst_day_revenue=worst_revenue,
        total_visits=unique_days,
        data_since=start_date.date(),
    )


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
    - Weather forecast (TODO)
    - Local events (TODO)
    - Cart count optimization

    Returns ranked recommendations with predicted revenue and confidence.
    """
    # Get all locations for the org
    locations = await location_service.list_by_org(org_id)

    if not locations:
        return []

    # Calculate day of week for target date
    day_of_week = (target_date.weekday() + 1) % 7  # Convert to Sunday=0
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    day_name = day_names[day_of_week]

    recommendations = []

    for location in locations:
        # Get historical data for this location
        end_date = datetime.now()
        start_date = end_date - __import__("datetime").timedelta(days=60)

        transactions = await transaction_service.list_by_date_range(
            org_id=org_id,
            start_date=start_date.isoformat() + "Z",
            end_date=end_date.isoformat() + "Z",
            location_id=location["id"],
        )

        # Filter to same day of week
        same_day_transactions = [
            t for t in transactions if t.get("day_of_week") == day_of_week
        ]

        if not same_day_transactions:
            # No data for this day, use overall average
            if transactions:
                predicted = sum(t["amount"] for t in transactions) / len(set(t["timestamp"][:10] for t in transactions))
                confidence = "LOW"
                reasons = [f"No {day_name} data, using overall average"]
            else:
                predicted = 0
                confidence = "LOW"
                reasons = ["No historical data for this location"]
        else:
            # Calculate average for this day of week
            day_revenue = sum(t["amount"] for t in same_day_transactions)
            day_count = len(set(t["timestamp"][:10] for t in same_day_transactions))
            predicted = day_revenue / day_count if day_count > 0 else 0

            # Determine confidence based on data points
            if day_count >= 4:
                confidence = "HIGH"
            elif day_count >= 2:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            # Build reasons
            reasons = []

            # Check for special day patterns
            location_notes = location.get("notes", "") or ""
            if "jury" in location_notes.lower() and day_name == "Thursday":
                reasons.append(f"{day_name} is jury duty day (+74% vs average)")
            elif "renewal" in location_notes.lower() and day_name == "Tuesday":
                reasons.append(f"{day_name} is renewal day - best revenue")
            else:
                reasons.append(f"Based on {day_count} previous {day_name}s")

            # Add location type context
            if location.get("location_type"):
                reasons.append(f"Location type: {location['location_type']}")

        recommendations.append(
            LocationRecommendation(
                location_id=location["id"],
                location_name=location["name"],
                predicted_revenue=round(predicted, 2),
                confidence=confidence,
                reasons=reasons,
            )
        )

    # Sort by predicted revenue (highest first)
    recommendations.sort(key=lambda x: x.predicted_revenue, reverse=True)

    return recommendations


@router.get("/{location_id}/compare")
async def compare_location(
    location_id: str,
    compare_to: List[str] = Query(..., description="Location IDs to compare"),
):
    """
    Compare performance between locations.

    Helps answer: "Should I move from DMV to Courthouse?"
    """
    # Get performance for primary location
    primary = await get_location_performance(location_id)

    comparisons = []
    for comp_id in compare_to:
        try:
            comp = await get_location_performance(comp_id)
            diff = comp.average_daily_revenue - primary.average_daily_revenue
            diff_pct = (diff / primary.average_daily_revenue * 100) if primary.average_daily_revenue > 0 else 0

            comparisons.append({
                "location_id": comp_id,
                "location_name": comp.location_name,
                "average_daily_revenue": comp.average_daily_revenue,
                "difference": round(diff, 2),
                "difference_percent": round(diff_pct, 1),
                "best_day": comp.best_day,
                "recommendation": "Switch" if diff > 50 else "Stay" if diff < -50 else "Similar"
            })
        except HTTPException:
            continue

    return {
        "primary": {
            "location_id": location_id,
            "location_name": primary.location_name,
            "average_daily_revenue": primary.average_daily_revenue,
            "best_day": primary.best_day,
        },
        "comparisons": comparisons,
    }
