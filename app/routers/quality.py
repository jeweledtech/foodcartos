"""
Quality Checks Router

Handles photo verification and quality scoring.
This is how Poncho ensures garlic butter buns happen even when he's not there.
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

router = APIRouter()


# ===========================================
# Models
# ===========================================


class QualityCheck(BaseModel):
    """A single quality check submission."""

    id: str
    cart_id: str
    employee_id: str
    employee_name: str
    check_type: str  # dirty_water, garlic_butter, cart_display
    photo_url: str
    status: str  # pending, approved, rejected
    notes: Optional[str] = None
    timestamp: datetime


class DailyChecklist(BaseModel):
    """Daily checklist status for a cart."""

    cart_id: str
    cart_name: str
    date: date
    required_checks: List[str]
    completed_checks: List[str]
    missing_checks: List[str]
    complete: bool
    completion_time: Optional[datetime] = None
    late: bool


class QualityScore(BaseModel):
    """Quality score for an employee over a period."""

    employee_id: str
    employee_name: str
    period_start: date
    period_end: date
    total_required: int
    total_completed: int
    score: float  # percentage
    on_time_percentage: float
    issues: List[dict]  # Recent problems


class Leaderboard(BaseModel):
    """Quality leaderboard for the organization."""

    period: str  # week, month
    rankings: List[dict]


# ===========================================
# Endpoints
# ===========================================


@router.get("/checks", response_model=List[QualityCheck])
async def list_quality_checks(
    org_id: str = Query(..., description="Organization ID"),
    date: date = Query(..., description="Date"),
    cart_id: Optional[str] = Query(None, description="Filter by cart"),
    employee_id: Optional[str] = Query(None, description="Filter by employee"),
):
    """
    List quality checks for a date.

    Returns all photo submissions with their status.
    """
    # TODO: Implement with Supabase
    return [
        {
            "id": "qc_1",
            "cart_id": "cart_1",
            "employee_id": "emp_poncho",
            "employee_name": "Poncho",
            "check_type": "dirty_water",
            "photo_url": "https://storage.supabase.co/photos/qc_1.jpg",
            "status": "approved",
            "notes": None,
            "timestamp": datetime.now(),
        },
        {
            "id": "qc_2",
            "cart_id": "cart_1",
            "employee_id": "emp_poncho",
            "employee_name": "Poncho",
            "check_type": "garlic_butter",
            "photo_url": "https://storage.supabase.co/photos/qc_2.jpg",
            "status": "approved",
            "notes": None,
            "timestamp": datetime.now(),
        },
    ]


@router.post("/checks", status_code=status.HTTP_201_CREATED)
async def submit_quality_check(
    cart_id: str = Query(..., description="Cart ID"),
    employee_id: str = Query(..., description="Employee ID"),
    check_type: str = Query(..., description="Type: dirty_water, garlic_butter, cart_display"),
    photo: UploadFile = File(..., description="Photo proof"),
):
    """
    Submit a quality check with photo.

    This is called from the employee app when they complete
    a checklist item with photo proof.

    Triggers n8n workflow for notification if checklist is complete.
    """
    # Validate check type
    valid_types = ["dirty_water", "garlic_butter", "cart_display"]
    if check_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid check type. Must be one of: {valid_types}",
        )

    # TODO: Implement
    # 1. Upload photo to Supabase Storage
    # 2. Create quality_check record
    # 3. Check if all required checks complete
    # 4. Trigger n8n webhook if complete

    return {
        "id": "qc_new",
        "status": "pending",
        "message": "Quality check submitted successfully",
    }


@router.get("/checklist/{cart_id}", response_model=DailyChecklist)
async def get_daily_checklist(
    cart_id: str,
    date: date = Query(..., description="Date"),
):
    """
    Get daily checklist status for a cart.

    Shows what's required, what's done, and what's missing.
    """
    # TODO: Implement with Supabase
    return {
        "cart_id": cart_id,
        "cart_name": "Cart 1 - Main",
        "date": date,
        "required_checks": ["dirty_water", "garlic_butter", "cart_display"],
        "completed_checks": ["dirty_water", "garlic_butter"],
        "missing_checks": ["cart_display"],
        "complete": False,
        "completion_time": None,
        "late": True,  # Past 11 AM deadline
    }


@router.get("/scores/{employee_id}", response_model=QualityScore)
async def get_employee_quality_score(
    employee_id: str,
    start_date: date = Query(..., description="Period start"),
    end_date: date = Query(..., description="Period end"),
):
    """
    Get quality score for an employee.

    This is what triggers the alert:
    "Cart 2 (Brother-in-law) has scored below 80% for 3 consecutive days."
    """
    # TODO: Implement with Supabase aggregation
    return {
        "employee_id": employee_id,
        "employee_name": "Brother-in-law",
        "period_start": start_date,
        "period_end": end_date,
        "total_required": 21,  # 7 days × 3 checks
        "total_completed": 15,
        "score": 71.4,  # Below 80% threshold!
        "on_time_percentage": 60.0,
        "issues": [
            {"date": "2024-01-15", "missing": ["garlic_butter"], "late": True},
            {"date": "2024-01-14", "missing": [], "late": True},
            {"date": "2024-01-13", "missing": ["garlic_butter", "cart_display"], "late": False},
        ],
    }


@router.get("/leaderboard", response_model=Leaderboard)
async def get_quality_leaderboard(
    org_id: str = Query(..., description="Organization ID"),
    period: str = Query("week", description="Period: week or month"),
):
    """
    Get quality leaderboard.

    Creates healthy competition between employees.
    Top performers get recognition (and maybe that AC trailer!).
    """
    # TODO: Implement with Supabase aggregation
    return {
        "period": period,
        "rankings": [
            {
                "rank": 1,
                "employee_id": "emp_poncho",
                "employee_name": "Poncho",
                "score": 100.0,
                "streak_days": 30,
            },
            {
                "rank": 2,
                "employee_id": "emp_new",
                "employee_name": "New Hire",
                "score": 95.2,
                "streak_days": 7,
            },
            {
                "rank": 3,
                "employee_id": "emp_brother",
                "employee_name": "Brother-in-law",
                "score": 71.4,
                "streak_days": 0,  # Broken streak
            },
        ],
    }


@router.patch("/checks/{check_id}")
async def update_check_status(
    check_id: str,
    status: str = Query(..., description="New status: approved or rejected"),
    notes: Optional[str] = Query(None, description="Reviewer notes"),
):
    """
    Update quality check status (owner review).

    Allows owner to approve or reject submitted photos.
    """
    valid_statuses = ["approved", "rejected"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    # TODO: Implement with Supabase
    return {"id": check_id, "status": status, "notes": notes}
