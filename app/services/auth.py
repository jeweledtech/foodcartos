"""
Authentication Service

Handles registration and login using Supabase as the user store.
Passwords are hashed with bcrypt via passlib.
Used by both page routes (session auth) and API routes (JWT auth).
"""

import logging
import re
from typing import Optional

import bcrypt

from app.services.supabase import SupabaseService, OrganizationService, UserService

logger = logging.getLogger(__name__)

# Admin-level DB access — auth operations bypass RLS
_db = SupabaseService(use_admin=True)
_org_service = OrganizationService(use_admin=True)
_user_service = UserService(use_admin=True)


def _slugify(name: str) -> str:
    """Turn a business name into a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


class AuthService:
    """Registration and credential verification."""

    async def register(
        self,
        business_name: str,
        owner_name: str,
        email: str,
        phone: str = "",
        password: str = "",
    ) -> Optional[dict]:
        """
        Create a new organization and owner user.

        Returns {"org": {...}, "user": {...}} or None on failure.
        """
        slug = _slugify(business_name)

        try:
            # Create organization
            org = await _org_service.create(name=business_name, slug=slug)
            if not org:
                return None

            # Hash password and create user
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user_data = {
                "org_id": org["id"],
                "email": email,
                "name": owner_name,
                "role": "owner",
                "phone": phone or None,
                "settings": {
                    "password_hash": hashed,
                    "onboarding_complete": False,
                    "onboarding_step": 2,
                },
            }
            result = _db.table("users").insert(user_data).execute()
            user = result.data[0] if result.data else None

            if not user:
                return None

            return {"org": org, "user": user}
        except Exception as e:
            logger.error("Registration failed: %s", e)
            return None

    async def login(self, email: str, password: str) -> Optional[dict]:
        """
        Verify credentials and return the user record, or None.
        """
        result = _db.table("users").select("*").eq("email", email).execute()
        if not result.data:
            return None

        user = result.data[0]
        user_settings = user.get("settings", {}) or {}
        stored_hash = user_settings.get("password_hash", "")

        if not stored_hash or not bcrypt.checkpw(password.encode(), stored_hash.encode()):
            return None

        # Promote settings fields to top-level for convenience
        user["onboarding_complete"] = user_settings.get("onboarding_complete", False)
        user["onboarding_step"] = user_settings.get("onboarding_step", 2)

        return user

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        result = _db.table("users").select("*").eq("id", user_id).execute()
        return result.data[0] if result.data else None


auth_service = AuthService()
