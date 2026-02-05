"""
Transactions Router

Handles revenue data from Square POS.
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


# ===========================================
# Models
# ===========================================


class Transaction(BaseModel):
    """A single transaction from Square."""

    id: str
    square_id: str
    cart_id: str
    location_id: str
    amount: float
    items: List[dict]  # [{"name": "Dirty Water Dog", "quantity": 2, "price": 10.00}]
    timestamp: datetime
    payment_method: str  # card, cash


class DailySummary(BaseModel):
    """Daily revenue summary."""

    date: date
    total_revenue: float
    transaction_count: int
    average_transaction: float
    by_cart: List[dict]
    by_location: List[dict]
    comparison_to_average: float  # percentage (+12%, -8%, etc.)


class RevenueTrend(BaseModel):
    """Revenue trend over time."""

    period: str  # daily, weekly, monthly
    data: List[dict]  # [{"date": "2024-01-15", "revenue": 1847.00}]
    total: float
    average: float
    best_day: dict
    worst_day: dict


# ===========================================
# Endpoints
# ===========================================


@router.get("/", response_model=List[Transaction])
async def list_transactions(
    org_id: str = Query(..., description="Organization ID"),
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    cart_id: Optional[str] = Query(None, description="Filter by cart"),
    location_id: Optional[str] = Query(None, description="Filter by location"),
    limit: int = Query(100, description="Max results"),
):
    """
    List transactions within a date range.

    Supports filtering by cart and/or location.
    """
    # TODO: Implement with Supabase
    return [
        {
            "id": "txn_1",
            "square_id": "sq_abc123",
            "cart_id": "cart_1",
            "location_id": "loc_1",
            "amount": 32.00,
            "items": [
                {"name": "Dirty Water Dog", "quantity": 2, "price": 10.00},
                {"name": "Brisket Dog", "quantity": 1, "price": 14.00},
            ],
            "timestamp": datetime.now(),
            "payment_method": "card",
        }
    ]


@router.get("/summary/daily", response_model=DailySummary)
async def get_daily_summary(
    org_id: str = Query(..., description="Organization ID"),
    date: date = Query(..., description="Date to summarize"),
):
    """
    Get daily revenue summary.

    This is what Poncho sees in his evening SMS:
    "Today: $1,847 across 3 carts"
    """
    # TODO: Implement with Supabase aggregation
    return {
        "date": date,
        "total_revenue": 1847.00,
        "transaction_count": 142,
        "average_transaction": 13.01,
        "by_cart": [
            {"cart_id": "cart_1", "cart_name": "Cart 1 - Main", "revenue": 892.00},
            {"cart_id": "cart_2", "cart_name": "Cart 2", "revenue": 610.00},
            {"cart_id": "cart_3", "cart_name": "Cart 3", "revenue": 345.00},
        ],
        "by_location": [
            {"location_id": "loc_1", "location_name": "Courthouse", "revenue": 892.00},
            {"location_id": "loc_2", "location_name": "DMV", "revenue": 610.00},
            {"location_id": "loc_3", "location_name": "Downtown", "revenue": 345.00},
        ],
        "comparison_to_average": 12.5,  # +12.5% vs 30-day average
    }


@router.get("/trends", response_model=RevenueTrend)
async def get_revenue_trends(
    org_id: str = Query(..., description="Organization ID"),
    period: str = Query("daily", description="Aggregation period: daily, weekly, monthly"),
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
):
    """
    Get revenue trends over time.

    Used for dashboard charts and identifying patterns.
    """
    # TODO: Implement with Supabase aggregation
    return {
        "period": period,
        "data": [
            {"date": "2024-01-15", "revenue": 1847.00},
            {"date": "2024-01-14", "revenue": 1623.00},
            {"date": "2024-01-13", "revenue": 1920.00},
        ],
        "total": 5390.00,
        "average": 1796.67,
        "best_day": {"date": "2024-01-13", "revenue": 1920.00},
        "worst_day": {"date": "2024-01-14", "revenue": 1623.00},
    }


@router.get("/compare")
async def compare_periods(
    org_id: str = Query(..., description="Organization ID"),
    period1_start: date = Query(...),
    period1_end: date = Query(...),
    period2_start: date = Query(...),
    period2_end: date = Query(...),
):
    """
    Compare revenue between two periods.

    Useful for week-over-week or month-over-month comparisons.
    """
    # TODO: Implement comparison logic
    return {
        "period1": {
            "start": period1_start,
            "end": period1_end,
            "total": 5000.00,
        },
        "period2": {
            "start": period2_start,
            "end": period2_end,
            "total": 5800.00,
        },
        "change": 800.00,
        "change_percent": 16.0,
    }
