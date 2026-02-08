"""
Page Routes — Server-rendered HTML via Jinja2 + HTMX.

All browser-facing pages live here.
API routes (/api/*) remain separate for mobile app / integrations.
"""

import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.supabase import (
    CartService,
    LocationService,
    OrganizationService,
    QualityCheckService,
    SupabaseService,
    TransactionService,
    UserService,
)

# Page routes use admin services to bypass RLS (session auth, not JWT)
organization_service = OrganizationService(use_admin=True)
user_service = UserService(use_admin=True)
location_service = LocationService(use_admin=True)
cart_service = CartService(use_admin=True)
transaction_service = TransactionService(use_admin=True)
quality_check_service = QualityCheckService(use_admin=True)

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Admin DB access for page routes
_db = SupabaseService(use_admin=True)

ONBOARDING_TOTAL_STEPS = 7


# ─── Helpers ───────────────────────────────────────────────

def _session(request: Request) -> dict:
    """Shorthand for request.session."""
    return request.session


def _redirect(url: str, hx_request: bool = False):
    """Return redirect — uses HX-Redirect header for HTMX requests."""
    if hx_request:
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = url
        return response
    return RedirectResponse(url, status_code=303)


def _flash(request: Request, message: str, flash_type: str = "info"):
    """Store a flash message in the session."""
    request.session["flash_message"] = message
    request.session["flash_type"] = flash_type


def _pop_flash(request: Request) -> dict:
    """Pop flash message from session into template context."""
    msg = request.session.pop("flash_message", None)
    ftype = request.session.pop("flash_type", "info")
    return {"flash_message": msg, "flash_type": ftype}


def _ctx(request: Request, **kwargs) -> dict:
    """Build common template context."""
    ctx = {
        "request": request,
        "session": request.session,
        "settings": settings,
    }
    ctx.update(_pop_flash(request))
    ctx.update(kwargs)
    return ctx


def _require_auth(request: Request):
    """Return a redirect if not authenticated, else None."""
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)
    return None


# ─── Root ──────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=303)
    return RedirectResponse("/login", status_code=303)


# ─── Auth Pages ────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("auth/login.html", _ctx(request))


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    from app.services.auth import auth_service

    user = await auth_service.login(email, password)
    if not user:
        _flash(request, "Invalid email or password.", "error")
        return templates.TemplateResponse("auth/login.html", _ctx(request))

    # Set session
    request.session["user_id"] = user["id"]
    request.session["org_id"] = user["org_id"]
    request.session["role"] = user["role"]
    request.session["name"] = user["name"]
    request.session["onboarding_complete"] = user.get("onboarding_complete", False)

    is_htmx = request.headers.get("HX-Request") == "true"

    if not user.get("onboarding_complete", False):
        step = user.get("onboarding_step", 2)
        return _redirect(f"/onboarding/step/{step}", is_htmx)

    return _redirect("/dashboard", is_htmx)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Redirect to onboarding step 1 — registration IS step 1."""
    return RedirectResponse("/onboarding/step/1", status_code=303)


# ─── Onboarding ───────────────────────────────────────────

@router.get("/onboarding/step/1", response_class=HTMLResponse)
async def onboarding_step_1(request: Request):
    return templates.TemplateResponse(
        "onboarding/welcome.html",
        _ctx(request, current_step=1, total_steps=ONBOARDING_TOTAL_STEPS),
    )


@router.post("/onboarding/step/1", response_class=HTMLResponse)
async def onboarding_step_1_submit(
    request: Request,
    business_name: str = Form(...),
    owner_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    password: str = Form(...),
):
    from app.services.auth import auth_service

    # Check if email already exists
    existing = await user_service.get_by_email(email)
    if existing:
        _flash(request, "An account with that email already exists. Please log in.", "error")
        return templates.TemplateResponse(
            "onboarding/welcome.html",
            _ctx(request, current_step=1, total_steps=ONBOARDING_TOTAL_STEPS),
        )

    result = await auth_service.register(
        business_name=business_name,
        owner_name=owner_name,
        email=email,
        phone=phone,
        password=password,
    )
    if not result:
        _flash(request, "Registration failed. Please try again.", "error")
        return templates.TemplateResponse(
            "onboarding/welcome.html",
            _ctx(request, current_step=1, total_steps=ONBOARDING_TOTAL_STEPS),
        )

    # Set session
    request.session["user_id"] = result["user"]["id"]
    request.session["org_id"] = result["org"]["id"]
    request.session["role"] = "owner"
    request.session["name"] = owner_name
    request.session["onboarding_complete"] = False
    request.session["onboarding_step"] = 2

    is_htmx = request.headers.get("HX-Request") == "true"
    return _redirect("/onboarding/step/2", is_htmx)


@router.get("/onboarding/step/2", response_class=HTMLResponse)
async def onboarding_step_2(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir
    return templates.TemplateResponse(
        "onboarding/square_connect.html",
        _ctx(request, current_step=2, total_steps=ONBOARDING_TOTAL_STEPS),
    )


@router.post("/onboarding/step/2", response_class=HTMLResponse)
async def onboarding_step_2_submit(
    request: Request,
    square_token: str = Form(""),
):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]
    is_htmx = request.headers.get("HX-Request") == "true"

    if square_token.strip():
        # Save token to org settings
        org = await organization_service.get_by_id(org_id)
        org_settings = org.get("settings", {}) if org else {}
        org_settings["square_access_token"] = square_token.strip()
        _db.table("organizations").update({"settings": org_settings}).eq("id", org_id).execute()

        # Try to import Square locations
        try:
            from square.client import Client as SquareClient
            client = SquareClient(access_token=square_token.strip(), environment=settings.SQUARE_ENVIRONMENT)
            result = client.locations.list_locations()
            if not result.is_error():
                sq_locations = result.body.get("locations", [])
                for sq_loc in sq_locations:
                    addr = sq_loc.get("address", {})
                    await location_service.create(
                        org_id=org_id,
                        name=sq_loc.get("name", "Square Location"),
                        latitude=sq_loc.get("coordinates", {}).get("latitude", 0.0),
                        longitude=sq_loc.get("coordinates", {}).get("longitude", 0.0),
                        address=addr.get("address_line_1", ""),
                    )
                _flash(request, f"Connected! Imported {len(sq_locations)} location(s) from Square.", "success")
        except Exception as e:
            logger.warning("Square import failed: %s", e)
            _flash(request, "Square token saved but location import failed. You can add locations manually.", "info")

    request.session["onboarding_step"] = 3
    return _redirect("/onboarding/step/3", is_htmx)


@router.get("/onboarding/step/3", response_class=HTMLResponse)
async def onboarding_step_3(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]
    locations = await location_service.list_by_org(org_id)

    return templates.TemplateResponse(
        "onboarding/locations.html",
        _ctx(
            request,
            current_step=3,
            total_steps=ONBOARDING_TOTAL_STEPS,
            locations=locations,
        ),
    )


@router.post("/onboarding/step/3", response_class=HTMLResponse)
async def onboarding_step_3_submit(
    request: Request,
    location_name: str = Form(""),
    location_address: str = Form(""),
    location_type: str = Form(""),
    latitude: float = Form(0.0),
    longitude: float = Form(0.0),
):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]
    is_htmx = request.headers.get("HX-Request") == "true"

    if location_name.strip():
        await location_service.create(
            org_id=org_id,
            name=location_name.strip(),
            latitude=latitude,
            longitude=longitude,
            address=location_address.strip() or None,
            location_type=location_type.strip() or None,
        )
        _flash(request, f"Added location: {location_name}", "success")
        # Stay on step 3 to add more
        return _redirect("/onboarding/step/3", is_htmx)

    # No new location — advance
    request.session["onboarding_step"] = 4
    return _redirect("/onboarding/step/4", is_htmx)


@router.post("/onboarding/step/3/next", response_class=HTMLResponse)
async def onboarding_step_3_next(request: Request):
    """Explicit 'Continue' button to move past locations."""
    redir = _require_auth(request)
    if redir:
        return redir
    request.session["onboarding_step"] = 4
    is_htmx = request.headers.get("HX-Request") == "true"
    return _redirect("/onboarding/step/4", is_htmx)


@router.get("/onboarding/step/4", response_class=HTMLResponse)
async def onboarding_step_4(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]
    carts = await cart_service.list_by_org(org_id)
    locations = await location_service.list_by_org(org_id)

    return templates.TemplateResponse(
        "onboarding/carts.html",
        _ctx(
            request,
            current_step=4,
            total_steps=ONBOARDING_TOTAL_STEPS,
            carts=carts,
            locations=locations,
        ),
    )


@router.post("/onboarding/step/4", response_class=HTMLResponse)
async def onboarding_step_4_submit(
    request: Request,
    cart_name: str = Form(""),
):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]
    is_htmx = request.headers.get("HX-Request") == "true"

    if cart_name.strip():
        await cart_service.create(org_id=org_id, name=cart_name.strip())
        _flash(request, f"Added cart: {cart_name}", "success")
        return _redirect("/onboarding/step/4", is_htmx)

    request.session["onboarding_step"] = 5
    return _redirect("/onboarding/step/5", is_htmx)


@router.post("/onboarding/step/4/next", response_class=HTMLResponse)
async def onboarding_step_4_next(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir
    request.session["onboarding_step"] = 5
    is_htmx = request.headers.get("HX-Request") == "true"
    return _redirect("/onboarding/step/5", is_htmx)


@router.get("/onboarding/step/5", response_class=HTMLResponse)
async def onboarding_step_5(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir
    return templates.TemplateResponse(
        "onboarding/quality_setup.html",
        _ctx(request, current_step=5, total_steps=ONBOARDING_TOTAL_STEPS),
    )


@router.post("/onboarding/step/5", response_class=HTMLResponse)
async def onboarding_step_5_submit(
    request: Request,
    checks: list[str] = Form([]),
    deadline_hour: int = Form(11),
):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]
    is_htmx = request.headers.get("HX-Request") == "true"

    # Save quality settings to org
    org = await organization_service.get_by_id(org_id)
    org_settings = org.get("settings", {}) if org else {}
    org_settings["quality_checks"] = checks
    org_settings["quality_deadline_hour"] = deadline_hour
    _db.table("organizations").update({"settings": org_settings}).eq("id", org_id).execute()

    request.session["onboarding_step"] = 6
    return _redirect("/onboarding/step/6", is_htmx)


@router.get("/onboarding/step/6", response_class=HTMLResponse)
async def onboarding_step_6(
    request: Request,
    connected: Optional[str] = Query(None),
):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]

    if connected:
        _flash(request, f"Connected {connected}!", "success")

    # Fetch connected social accounts (table may not exist yet)
    try:
        result = _db.table("social_accounts").select("*").eq("org_id", org_id).eq("is_active", True).execute()
        accounts = result.data if result.data else []
    except Exception:
        accounts = []

    return templates.TemplateResponse(
        "onboarding/social_connect.html",
        _ctx(
            request,
            current_step=6,
            total_steps=ONBOARDING_TOTAL_STEPS,
            accounts=accounts,
        ),
    )


@router.post("/onboarding/step/6", response_class=HTMLResponse)
async def onboarding_step_6_submit(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir
    request.session["onboarding_step"] = 7
    is_htmx = request.headers.get("HX-Request") == "true"
    return _redirect("/onboarding/step/7", is_htmx)


@router.get("/onboarding/step/7", response_class=HTMLResponse)
async def onboarding_step_7(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]

    locations = await location_service.list_by_org(org_id)
    carts = await cart_service.list_by_org(org_id)

    # Try to get today's summary
    today_str = date.today().isoformat()
    try:
        summary = await transaction_service.get_daily_summary(org_id, today_str)
    except Exception:
        summary = None

    return templates.TemplateResponse(
        "onboarding/dashboard_preview.html",
        _ctx(
            request,
            current_step=7,
            total_steps=ONBOARDING_TOTAL_STEPS,
            locations=locations,
            carts=carts,
            summary=summary,
        ),
    )


@router.post("/onboarding/step/7", response_class=HTMLResponse)
async def onboarding_complete(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir

    user_id = request.session["user_id"]
    is_htmx = request.headers.get("HX-Request") == "true"

    # Mark onboarding complete in user settings JSONB
    user_result = _db.table("users").select("settings").eq("id", user_id).execute()
    user_settings = user_result.data[0].get("settings", {}) if user_result.data else {}
    user_settings["onboarding_complete"] = True
    _db.table("users").update({"settings": user_settings}).eq("id", user_id).execute()
    request.session["onboarding_complete"] = True
    request.session.pop("onboarding_step", None)

    _flash(request, "Welcome to FoodCartOS! Your dashboard is ready.", "success")
    return _redirect("/dashboard", is_htmx)


# ─── Dashboard ─────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]
    today_str = date.today().isoformat()

    try:
        summary = await transaction_service.get_daily_summary(org_id, today_str)
    except Exception:
        summary = {"total_revenue": 0, "transaction_count": 0, "average_transaction": 0, "by_cart": [], "by_location": []}

    carts = await cart_service.list_by_org(org_id)
    locations = await location_service.list_by_org(org_id)

    return templates.TemplateResponse(
        "dashboard/index.html",
        _ctx(
            request,
            summary=summary,
            carts=carts,
            locations=locations,
            today=today_str,
        ),
    )


@router.get("/dashboard/locations", response_class=HTMLResponse)
async def dashboard_locations(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]
    locations = await location_service.list_by_org(org_id)

    # Get performance for each location
    performances = []
    for loc in locations:
        try:
            end_dt = datetime.now()
            start_dt = end_dt - __import__("datetime").timedelta(days=30)
            txns = await transaction_service.list_by_date_range(
                org_id=org_id,
                start_date=start_dt.isoformat() + "Z",
                end_date=end_dt.isoformat() + "Z",
                location_id=loc["id"],
            )
            total = sum(t["amount"] for t in txns)
            days = len(set(t["timestamp"][:10] for t in txns))
            avg = total / days if days > 0 else 0
            performances.append({
                **loc,
                "total_revenue": round(total, 2),
                "visit_days": days,
                "avg_daily": round(avg, 2),
            })
        except Exception:
            performances.append({**loc, "total_revenue": 0, "visit_days": 0, "avg_daily": 0})

    return templates.TemplateResponse(
        "dashboard/locations.html",
        _ctx(request, performances=performances),
    )


@router.get("/dashboard/quality", response_class=HTMLResponse)
async def dashboard_quality(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]
    carts = await cart_service.list_by_org(org_id)

    # Get recent quality checks
    checks = []
    today_str = date.today().isoformat()
    for cart in carts:
        try:
            cart_checks = await quality_check_service.list_by_cart_date(cart["id"], today_str)
            for c in cart_checks:
                c["cart_name"] = cart.get("name", "Unknown")
            checks.extend(cart_checks)
        except Exception:
            pass

    return templates.TemplateResponse(
        "dashboard/quality.html",
        _ctx(request, checks=checks, carts=carts),
    )


@router.patch("/dashboard/quality/{check_id}", response_class=HTMLResponse)
async def review_quality_check(
    request: Request,
    check_id: str,
    status: str = Form(...),
):
    redir = _require_auth(request)
    if redir:
        return redir

    await quality_check_service.update_status(check_id, status, reviewer_id=request.session.get("user_id"))

    # Return updated badge for HTMX swap
    badge_class = "badge-success" if status == "approved" else "badge-danger"
    return HTMLResponse(f'<span class="badge {badge_class}">{status}</span>')


# ─── Settings ──────────────────────────────────────────────

@router.get("/settings/account", response_class=HTMLResponse)
async def settings_account(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir

    user_id = request.session["user_id"]
    org_id = request.session["org_id"]

    user = _db.table("users").select("*").eq("id", user_id).execute()
    org = await organization_service.get_by_id(org_id)

    return templates.TemplateResponse(
        "settings/account.html",
        _ctx(
            request,
            user=user.data[0] if user.data else {},
            org=org or {},
        ),
    )


@router.post("/settings/account", response_class=HTMLResponse)
async def settings_account_save(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    org_name: str = Form(""),
):
    redir = _require_auth(request)
    if redir:
        return redir

    user_id = request.session["user_id"]
    org_id = request.session["org_id"]
    is_htmx = request.headers.get("HX-Request") == "true"

    _db.table("users").update({"name": name, "email": email, "phone": phone}).eq("id", user_id).execute()
    if org_name.strip():
        _db.table("organizations").update({"name": org_name}).eq("id", org_id).execute()

    request.session["name"] = name
    _flash(request, "Settings saved.", "success")
    return _redirect("/settings/account", is_htmx)


@router.get("/settings/social", response_class=HTMLResponse)
async def settings_social(
    request: Request,
    connected: Optional[str] = Query(None),
):
    redir = _require_auth(request)
    if redir:
        return redir

    org_id = request.session["org_id"]

    if connected:
        _flash(request, f"Connected {connected}!", "success")

    # Table may not exist if social media migration hasn't been applied
    try:
        result = _db.table("social_accounts").select(
            "id, platform, platform_username, platform_page_id, is_active, settings, created_at"
        ).eq("org_id", org_id).execute()
        accounts = result.data if result.data else []
    except Exception:
        accounts = []

    return templates.TemplateResponse(
        "settings/social.html",
        _ctx(request, accounts=accounts),
    )
