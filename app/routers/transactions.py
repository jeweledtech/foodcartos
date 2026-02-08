"""
Transactions Router

Handles revenue data from Square POS.
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.supabase import transaction_service

router = APIRouter()


# ===========================================
# Models
# ===========================================


class Transaction(BaseModel):
    """A single transaction from Square."""

    id: str
    square_id: Optional[str] = None
    cart_id: Optional[str] = None
    location_id: Optional[str] = None
    amount: float
    items: List[dict]
    timestamp: datetime
    payment_method: Optional[str] = None


class DailySummary(BaseModel):
    """Daily revenue summary."""

    date: date
    total_revenue: float
    transaction_count: int
    average_transaction: float
    by_cart: List[dict]
    by_location: List[dict]
    comparison_to_average: Optional[float] = None


class RevenueTrend(BaseModel):
    """Revenue trend over time."""

    period: str
    data: List[dict]
    total: float
    average: float
    best_day: dict
    worst_day: dict


# ===========================================
# Endpoints
# ===========================================


@router.get("/", response_model=List[dict])
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
    start_str = f"{start_date}T00:00:00Z"
    end_str = f"{end_date}T23:59:59Z"

    transactions = await transaction_service.list_by_date_range(
        org_id=org_id,
        start_date=start_str,
        end_date=end_str,
        cart_id=cart_id,
        location_id=location_id,
    )

    return transactions[:limit]


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
    summary = await transaction_service.get_daily_summary(org_id, str(date))

    return DailySummary(
        date=date,
        total_revenue=summary["total_revenue"],
        transaction_count=summary["transaction_count"],
        average_transaction=summary["average_transaction"],
        by_cart=summary["by_cart"],
        by_location=summary["by_location"],
        comparison_to_average=None,  # TODO: Calculate vs 30-day average
    )


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
    start_str = f"{start_date}T00:00:00Z"
    end_str = f"{end_date}T23:59:59Z"

    transactions = await transaction_service.list_by_date_range(
        org_id=org_id,
        start_date=start_str,
        end_date=end_str,
    )

    # Group by day
    daily_totals = {}
    for t in transactions:
        day = t["timestamp"][:10]
        if day not in daily_totals:
            daily_totals[day] = 0
        daily_totals[day] += t["amount"]

    # Build trend data
    data = [{"date": day, "revenue": round(amount, 2)} for day, amount in sorted(daily_totals.items())]

    total = sum(d["revenue"] for d in data)
    average = total / len(data) if data else 0

    best_day = max(data, key=lambda x: x["revenue"]) if data else {"date": None, "revenue": 0}
    worst_day = min(data, key=lambda x: x["revenue"]) if data else {"date": None, "revenue": 0}

    return RevenueTrend(
        period=period,
        data=data,
        total=round(total, 2),
        average=round(average, 2),
        best_day=best_day,
        worst_day=worst_day,
    )


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
    # Get period 1 transactions
    p1_transactions = await transaction_service.list_by_date_range(
        org_id=org_id,
        start_date=f"{period1_start}T00:00:00Z",
        end_date=f"{period1_end}T23:59:59Z",
    )
    p1_total = sum(t["amount"] for t in p1_transactions)

    # Get period 2 transactions
    p2_transactions = await transaction_service.list_by_date_range(
        org_id=org_id,
        start_date=f"{period2_start}T00:00:00Z",
        end_date=f"{period2_end}T23:59:59Z",
    )
    p2_total = sum(t["amount"] for t in p2_transactions)

    change = p2_total - p1_total
    change_percent = (change / p1_total * 100) if p1_total > 0 else 0

    return {
        "period1": {
            "start": period1_start,
            "end": period1_end,
            "total": round(p1_total, 2),
            "transactions": len(p1_transactions),
        },
        "period2": {
            "start": period2_start,
            "end": period2_end,
            "total": round(p2_total, 2),
            "transactions": len(p2_transactions),
        },
        "change": round(change, 2),
        "change_percent": round(change_percent, 1),
    }
