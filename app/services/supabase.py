"""
Supabase Client Service

Provides database connection and operations for FoodCartOS.
Uses the dedicated 'foodcartos' schema.
"""

from functools import lru_cache
from typing import Optional

from supabase import create_client, Client

from app.config import settings


# Schema prefix for all queries
SCHEMA = settings.DATABASE_SCHEMA


@lru_cache()
def get_supabase() -> Client:
    """Get cached Supabase client instance (anon key - respects RLS)."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")

    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY
    )


@lru_cache()
def get_supabase_admin() -> Client:
    """Get cached Supabase client with service role (bypasses RLS)."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY
    )


# Global client instance
supabase_client = get_supabase() if settings.SUPABASE_URL else None
supabase_admin = get_supabase_admin() if settings.SUPABASE_SERVICE_KEY else None


class SupabaseService:
    """
    Base service class for Supabase operations.

    All queries automatically use the foodcartos schema.
    Note: Schema must be exposed in Supabase API settings.
    """

    def __init__(self, client: Optional[Client] = None, use_admin: bool = False):
        if use_admin:
            self.client = get_supabase_admin()
        else:
            self.client = client or get_supabase()
        self.schema = SCHEMA
        self._use_admin = use_admin

    def table(self, name: str):
        """Get a table reference with schema prefix."""
        return self.client.schema(self.schema).table(name)


class OrganizationService(SupabaseService):
    """Operations for organizations table."""

    async def create(self, name: str, slug: str, settings: dict = None) -> dict:
        """Create a new organization."""
        data = {
            "name": name,
            "slug": slug,
            "settings": settings or {}
        }
        result = self.table("organizations").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_by_slug(self, slug: str) -> Optional[dict]:
        """Get organization by slug."""
        result = self.table("organizations").select("*").eq("slug", slug).execute()
        return result.data[0] if result.data else None

    async def get_by_id(self, org_id: str) -> Optional[dict]:
        """Get organization by ID."""
        result = self.table("organizations").select("*").eq("id", org_id).execute()
        return result.data[0] if result.data else None

    async def list_all(self) -> list:
        """List all organizations."""
        result = self.table("organizations").select("*").execute()
        return result.data


class UserService(SupabaseService):
    """Operations for users table."""

    async def create(self, org_id: str, email: str, name: str, role: str, phone: str = None) -> dict:
        """Create a new user."""
        data = {
            "org_id": org_id,
            "email": email,
            "name": name,
            "role": role,
            "phone": phone
        }
        result = self.table("users").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_by_email(self, email: str) -> Optional[dict]:
        """Get user by email."""
        result = self.table("users").select("*").eq("email", email).execute()
        return result.data[0] if result.data else None

    async def list_by_org(self, org_id: str) -> list:
        """List users in an organization."""
        result = self.table("users").select("*").eq("org_id", org_id).execute()
        return result.data


class LocationService(SupabaseService):
    """Operations for locations table."""

    async def create(self, org_id: str, name: str, latitude: float, longitude: float,
                     address: str = None, location_type: str = None, notes: str = None) -> dict:
        """Create a new location."""
        data = {
            "org_id": org_id,
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "address": address,
            "location_type": location_type,
            "notes": notes
        }
        result = self.table("locations").insert(data).execute()
        return result.data[0] if result.data else None

    async def list_by_org(self, org_id: str, location_type: str = None) -> list:
        """List locations for an organization."""
        query = self.table("locations").select("*").eq("org_id", org_id)
        if location_type:
            query = query.eq("location_type", location_type)
        result = query.execute()
        return result.data

    async def get_by_id(self, location_id: str) -> Optional[dict]:
        """Get location by ID."""
        result = self.table("locations").select("*").eq("id", location_id).execute()
        return result.data[0] if result.data else None


class CartService(SupabaseService):
    """Operations for carts table."""

    async def create(self, org_id: str, name: str, hardware_id: str = None) -> dict:
        """Create a new cart."""
        data = {
            "org_id": org_id,
            "name": name,
            "hardware_id": hardware_id,
            "status": "inactive"
        }
        result = self.table("carts").insert(data).execute()
        return result.data[0] if result.data else None

    async def list_by_org(self, org_id: str) -> list:
        """List carts for an organization."""
        result = self.table("carts").select("*").eq("org_id", org_id).execute()
        return result.data

    async def update_status(self, cart_id: str, status: str) -> dict:
        """Update cart status."""
        result = self.table("carts").update({"status": status}).eq("id", cart_id).execute()
        return result.data[0] if result.data else None


class TransactionService(SupabaseService):
    """Operations for transactions table."""

    async def create(self, org_id: str, cart_id: str, location_id: str,
                     amount: float, timestamp: str, square_id: str = None,
                     items: list = None, payment_method: str = "card") -> dict:
        """Create a new transaction."""
        from datetime import datetime

        # Calculate day of week (0=Sunday in JS, but Python uses 0=Monday)
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        day_of_week = (dt.weekday() + 1) % 7  # Convert to Sunday=0

        data = {
            "org_id": org_id,
            "cart_id": cart_id,
            "location_id": location_id,
            "amount": amount,
            "timestamp": timestamp,
            "square_id": square_id,
            "items": items or [],
            "payment_method": payment_method,
            "day_of_week": day_of_week
        }
        result = self.table("transactions").insert(data).execute()
        return result.data[0] if result.data else None

    async def list_by_date_range(self, org_id: str, start_date: str, end_date: str,
                                  cart_id: str = None, location_id: str = None) -> list:
        """List transactions in a date range."""
        query = self.table("transactions").select("*").eq("org_id", org_id)
        query = query.gte("timestamp", start_date).lte("timestamp", end_date)

        if cart_id:
            query = query.eq("cart_id", cart_id)
        if location_id:
            query = query.eq("location_id", location_id)

        result = query.order("timestamp", desc=True).execute()
        return result.data

    async def get_daily_summary(self, org_id: str, date: str) -> dict:
        """Get daily revenue summary."""
        start = f"{date}T00:00:00Z"
        end = f"{date}T23:59:59Z"

        transactions = await self.list_by_date_range(org_id, start, end)

        total_revenue = sum(t["amount"] for t in transactions)
        transaction_count = len(transactions)

        # Group by cart
        by_cart = {}
        for t in transactions:
            cart_id = t["cart_id"]
            if cart_id not in by_cart:
                by_cart[cart_id] = {"cart_id": cart_id, "revenue": 0, "count": 0}
            by_cart[cart_id]["revenue"] += t["amount"]
            by_cart[cart_id]["count"] += 1

        # Group by location
        by_location = {}
        for t in transactions:
            loc_id = t["location_id"]
            if loc_id not in by_location:
                by_location[loc_id] = {"location_id": loc_id, "revenue": 0, "count": 0}
            by_location[loc_id]["revenue"] += t["amount"]
            by_location[loc_id]["count"] += 1

        return {
            "date": date,
            "total_revenue": total_revenue,
            "transaction_count": transaction_count,
            "average_transaction": total_revenue / transaction_count if transaction_count > 0 else 0,
            "by_cart": list(by_cart.values()),
            "by_location": list(by_location.values())
        }


class QualityCheckService(SupabaseService):
    """Operations for quality_checks table."""

    async def create(self, org_id: str, cart_id: str, employee_id: str,
                     check_type: str, photo_url: str = None) -> dict:
        """Create a new quality check."""
        data = {
            "org_id": org_id,
            "cart_id": cart_id,
            "employee_id": employee_id,
            "check_type": check_type,
            "photo_url": photo_url,
            "status": "pending"
        }
        result = self.table("quality_checks").insert(data).execute()
        return result.data[0] if result.data else None

    async def list_by_cart_date(self, cart_id: str, date: str) -> list:
        """List quality checks for a cart on a specific date."""
        start = f"{date}T00:00:00Z"
        end = f"{date}T23:59:59Z"

        result = self.table("quality_checks").select("*").eq("cart_id", cart_id)\
            .gte("timestamp", start).lte("timestamp", end).execute()
        return result.data

    async def update_status(self, check_id: str, status: str, reviewer_id: str = None,
                            notes: str = None) -> dict:
        """Update quality check status."""
        data = {"status": status}
        if reviewer_id:
            data["reviewer_id"] = reviewer_id
        if notes:
            data["reviewer_notes"] = notes

        result = self.table("quality_checks").update(data).eq("id", check_id).execute()
        return result.data[0] if result.data else None


class OrderService(SupabaseService):
    """Operations for orders table (multi-platform orders)."""

    async def create(self, org_id: str, platform: str, external_id: str = None,
                     cart_id: str = None, location_id: str = None,
                     customer_name: str = None, customer_phone: str = None,
                     customer_email: str = None, items: list = None,
                     subtotal: float = 0, tax: float = 0, tip: float = 0,
                     delivery_fee: float = 0, platform_fee: float = 0,
                     total: float = 0, status: str = "pending",
                     delivery: dict = None, raw_payload: dict = None) -> dict:
        """Create a new order from any platform."""
        data = {
            "org_id": org_id,
            "platform": platform,
            "external_id": external_id,
            "cart_id": cart_id,
            "location_id": location_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_email": customer_email,
            "items": items or [],
            "subtotal": subtotal,
            "tax": tax,
            "tip": tip,
            "delivery_fee": delivery_fee,
            "platform_fee": platform_fee,
            "total": total,
            "status": status,
            "delivery": delivery,
            "raw_payload": raw_payload,
        }
        result = self.table("orders").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_by_id(self, order_id: str) -> Optional[dict]:
        """Get order by ID."""
        result = self.table("orders").select("*").eq("id", order_id).execute()
        return result.data[0] if result.data else None

    async def get_by_external_id(self, platform: str, external_id: str) -> Optional[dict]:
        """Get order by platform and external ID."""
        result = self.table("orders").select("*")\
            .eq("platform", platform)\
            .eq("external_id", external_id)\
            .execute()
        return result.data[0] if result.data else None

    async def update_status(self, order_id: str, status: str,
                            confirmed_at: str = None, ready_at: str = None,
                            completed_at: str = None) -> dict:
        """Update order status."""
        data = {"status": status}
        if confirmed_at:
            data["confirmed_at"] = confirmed_at
        if ready_at:
            data["ready_at"] = ready_at
        if completed_at:
            data["completed_at"] = completed_at

        result = self.table("orders").update(data).eq("id", order_id).execute()
        return result.data[0] if result.data else None

    async def list_by_org(self, org_id: str, status: str = None,
                          platform: str = None, limit: int = 50) -> list:
        """List orders for an organization."""
        query = self.table("orders").select("*").eq("org_id", org_id)

        if status:
            query = query.eq("status", status)
        if platform:
            query = query.eq("platform", platform)

        result = query.order("created_at", desc=True).limit(limit).execute()
        return result.data

    async def list_active(self, org_id: str, cart_id: str = None) -> list:
        """List active orders (not completed or cancelled)."""
        query = self.table("orders").select("*").eq("org_id", org_id)

        if cart_id:
            query = query.eq("cart_id", cart_id)

        # Active = pending, confirmed, preparing, ready
        query = query.in_("status", ["pending", "confirmed", "preparing", "ready"])

        result = query.order("created_at", desc=False).execute()
        return result.data

    async def get_daily_order_stats(self, org_id: str, date: str) -> dict:
        """Get order statistics for a day."""
        start = f"{date}T00:00:00Z"
        end = f"{date}T23:59:59Z"

        result = self.table("orders").select("*")\
            .eq("org_id", org_id)\
            .gte("created_at", start)\
            .lte("created_at", end)\
            .execute()

        orders = result.data

        # Calculate stats
        by_platform = {}
        by_status = {}
        total_revenue = 0

        for order in orders:
            platform = order["platform"]
            status = order["status"]

            if platform not in by_platform:
                by_platform[platform] = {"count": 0, "revenue": 0}
            by_platform[platform]["count"] += 1
            by_platform[platform]["revenue"] += order["total"]

            if status not in by_status:
                by_status[status] = 0
            by_status[status] += 1

            if status not in ["cancelled", "refunded"]:
                total_revenue += order["total"]

        return {
            "date": date,
            "total_orders": len(orders),
            "total_revenue": round(total_revenue, 2),
            "by_platform": by_platform,
            "by_status": by_status,
        }


# Service instances
organization_service = OrganizationService()
user_service = UserService()
location_service = LocationService()
cart_service = CartService()
transaction_service = TransactionService()
quality_check_service = QualityCheckService()
order_service = OrderService()
