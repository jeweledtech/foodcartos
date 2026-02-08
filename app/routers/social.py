"""
Social Media Router

Endpoints for managing social accounts, posts, approval callbacks,
and OAuth flows for Instagram, Facebook, TikTok, and Google Business Profile.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import settings
from app.services.social_media import (
    SocialPlatform,
    PostStatus,
    SocialPost,
    PostMedia,
    PostTrigger,
    content_generator_service,
    post_publisher_service,
    instagram_service,
    facebook_service,
    tiktok_service,
    google_business_service,
)
from app.services.supabase import SupabaseService

logger = logging.getLogger(__name__)

router = APIRouter()

# Admin service for direct DB access in endpoints
_social_db = SupabaseService(use_admin=True)

# Map platform names to service instances
PLATFORM_SERVICES = {
    "instagram": instagram_service,
    "facebook": facebook_service,
    "tiktok": tiktok_service,
    "google_business": google_business_service,
}


# ===========================================
# Request/Response Models
# ===========================================


class ConnectAccountRequest(BaseModel):
    platform: str
    auth_code: str
    redirect_uri: str


class UpdateSettingsRequest(BaseModel):
    settings: dict


class CreatePostRequest(BaseModel):
    caption: str
    media_urls: list[str] = []
    hashtags: list[str] = []
    platforms: list[str] = []
    scheduled_for: Optional[str] = None


class EditPostRequest(BaseModel):
    caption: str
    hashtags: list[str] = []


class AccountResponse(BaseModel):
    id: str
    platform: str
    platform_username: Optional[str] = None
    platform_page_id: Optional[str] = None
    is_active: bool
    settings: dict
    created_at: str


# ===========================================
# Account Management
# ===========================================


@router.get("/accounts")
async def list_accounts(
    org_id: str = Query(..., description="Organization ID"),
):
    """
    List connected social media accounts.

    Tokens are masked in the response for security.
    """
    result = (
        _social_db.table("social_accounts")
        .select("id, org_id, platform, platform_username, platform_page_id, is_active, settings, created_at")
        .eq("org_id", org_id)
        .execute()
    )
    return result.data


@router.post("/accounts/connect", status_code=status.HTTP_201_CREATED)
async def connect_account(
    body: ConnectAccountRequest,
    org_id: str = Query(..., description="Organization ID"),
):
    """
    Connect a social media account via OAuth authorization code.

    Exchanges the code for access tokens and saves the account.
    """
    platform_str = body.platform
    service = PLATFORM_SERVICES.get(platform_str)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: {platform_str}",
        )

    try:
        tokens = await service.authenticate(body.auth_code, body.redirect_uri)
    except Exception as e:
        logger.error("OAuth exchange failed for %s: %s", platform_str, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth exchange failed: {str(e)}",
        )

    # Build account record
    now = datetime.now(timezone.utc).isoformat()
    account_data = {
        "org_id": org_id,
        "platform": platform_str,
        "access_token": tokens.get("access_token", ""),
        "refresh_token": tokens.get("refresh_token", ""),
        "token_expires_at": None,
        "platform_user_id": tokens.get("user_id") or tokens.get("open_id", ""),
        "platform_username": tokens.get("page_name", ""),
        "platform_page_id": tokens.get("page_id") or tokens.get("location_name", ""),
        "is_active": True,
        "settings": {
            "auto_approve_quality_check": False,
            "auto_approve_location_arrival": False,
            "auto_approve_milestone": False,
            "auto_approve_manual": False,
            "auto_approve_new_location": False,
            "auto_approve_order_volume": False,
        },
    }

    if tokens.get("expires_in"):
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
        account_data["token_expires_at"] = expires_at.isoformat()

    result = _social_db.table("social_accounts").insert(account_data).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save account",
        )

    saved = result.data[0]
    # Don't expose tokens in response
    saved.pop("access_token", None)
    saved.pop("refresh_token", None)
    return saved


@router.delete("/accounts/{account_id}")
async def disconnect_account(account_id: str):
    """Disconnect (deactivate) a social media account."""
    result = (
        _social_db.table("social_accounts")
        .update({"is_active": False})
        .eq("id", account_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return {"status": "disconnected", "account_id": account_id}


@router.patch("/accounts/{account_id}/settings")
async def update_account_settings(
    account_id: str,
    body: UpdateSettingsRequest,
):
    """
    Update auto-approve settings for a social account.

    Settings keys: auto_approve_quality_check, auto_approve_location_arrival, etc.
    """
    result = (
        _social_db.table("social_accounts")
        .select("settings")
        .eq("id", account_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Merge new settings into existing
    current_settings = result.data[0].get("settings", {})
    current_settings.update(body.settings)

    update_result = (
        _social_db.table("social_accounts")
        .update({"settings": current_settings})
        .eq("id", account_id)
        .execute()
    )
    return update_result.data[0] if update_result.data else {"status": "updated"}


# ===========================================
# Post Management
# ===========================================


@router.get("/posts")
async def list_posts(
    org_id: str = Query(..., description="Organization ID"),
    post_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, le=100),
):
    """List social posts for an organization."""
    return await post_publisher_service.list_posts(org_id, status=post_status, limit=limit)


@router.post("/posts", status_code=status.HTTP_201_CREATED)
async def create_post(
    body: CreatePostRequest,
    org_id: str = Query(..., description="Organization ID"),
    owner_phone: Optional[str] = Query(None, description="Phone for SMS approval"),
):
    """
    Create a manual social media post.

    If auto-approve is enabled for manual posts, publishes immediately.
    Otherwise sends an SMS approval to the owner.
    """
    media = [PostMedia(url=url) for url in body.media_urls]
    target_platforms = [SocialPlatform(p) for p in body.platforms] if body.platforms else []

    # If no platforms specified, use all active ones
    if not target_platforms:
        accounts = await post_publisher_service.get_active_accounts(org_id)
        target_platforms = [SocialPlatform(a["platform"]) for a in accounts]

    post = SocialPost(
        caption=body.caption,
        media=media,
        hashtags=body.hashtags,
        trigger_type=PostTrigger.MANUAL,
        status=PostStatus.DRAFT,
        target_platforms=target_platforms,
        org_id=org_id,
    )

    result = await post_publisher_service.handle_new_post(post, org_id, owner_phone)
    return result


@router.get("/posts/{post_id}")
async def get_post(post_id: str):
    """Get a single social post by ID."""
    post = await post_publisher_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


@router.delete("/posts/{post_id}")
async def archive_post(post_id: str):
    """Archive (delete) a social post."""
    success = await post_publisher_service.delete_post(post_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return {"status": "deleted", "post_id": post_id}


@router.get("/analytics/{post_id}")
async def get_post_analytics(post_id: str):
    """
    Fetch platform analytics for a published post.

    Queries each platform's API for engagement metrics.
    """
    post = await post_publisher_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post["status"] != "published":
        return {"post_id": post_id, "status": post["status"], "analytics": {}}

    org_id = post["org_id"]
    accounts = await post_publisher_service.get_active_accounts(org_id)
    accounts_by_platform = {a["platform"]: a for a in accounts}

    analytics = {}
    platform_post_ids = post.get("platform_post_ids", {})

    for platform_str, platform_post_id in platform_post_ids.items():
        service = PLATFORM_SERVICES.get(platform_str)
        account = accounts_by_platform.get(platform_str)
        if service and account:
            try:
                data = await service.get_post_analytics(
                    account["access_token"], platform_post_id
                )
                analytics[platform_str] = data
            except Exception as e:
                analytics[platform_str] = {"error": str(e)}

    return {"post_id": post_id, "analytics": analytics}


# ===========================================
# Approval Callbacks (from SMS links)
# ===========================================


@router.get("/approve/{post_id}")
async def approve_post(post_id: str):
    """
    Approve and publish a pending post.

    Called when owner taps the Approve link in SMS.
    """
    post = await post_publisher_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post["status"] not in ("pending_approval", "draft"):
        return {"status": post["status"], "message": f"Post already {post['status']}"}

    result = await post_publisher_service.approve_post(post_id, approved_by="sms")
    return result


@router.get("/skip/{post_id}")
async def skip_post(post_id: str):
    """
    Reject/skip a pending post.

    Called when owner taps the Skip link in SMS.
    """
    post = await post_publisher_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post["status"] not in ("pending_approval", "draft"):
        return {"status": post["status"], "message": f"Post already {post['status']}"}

    return await post_publisher_service.reject_post(post_id)


@router.get("/edit/{post_id}")
async def get_post_for_edit(post_id: str):
    """
    Get post data for editing.

    Called when owner taps the Edit link in SMS.
    Returns the current caption and hashtags.
    """
    post = await post_publisher_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    return {
        "post_id": post_id,
        "caption": post["caption"],
        "hashtags": post.get("hashtags", []),
        "media_urls": post.get("media_urls", []),
        "status": post["status"],
    }


@router.patch("/edit/{post_id}")
async def save_edit_and_approve(
    post_id: str,
    body: EditPostRequest,
):
    """
    Save edited caption/hashtags and approve the post.

    Called after owner edits the post content.
    """
    post = await post_publisher_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Update caption and hashtags
    _social_db.table("social_posts").update({
        "caption": body.caption,
        "hashtags": body.hashtags,
    }).eq("id", post_id).execute()

    # Approve and publish
    result = await post_publisher_service.approve_post(post_id, approved_by="sms_edit")
    return result


# ===========================================
# OAuth Callbacks
# ===========================================


def _parse_oauth_state(state: str) -> tuple[str, str]:
    """
    Parse OAuth state parameter.

    State format: "org_id|context" where context is "onboarding" or "settings".
    Falls back to treating the whole string as org_id with "settings" context.
    """
    if "|" in state:
        org_id, context = state.split("|", 1)
        return org_id, context
    return state, "settings"


def _oauth_redirect_url(context: str, platform: str, error: bool = False) -> str:
    """Build redirect URL based on OAuth context (onboarding vs settings)."""
    if error:
        param = f"error={platform}_auth_failed"
    else:
        param = f"connected={platform}"

    if context == "onboarding":
        return f"/onboarding/step/6?{param}"
    return f"/settings/social?{param}"


@router.get("/instagram/callback")
async def instagram_oauth_callback(
    code: str = Query(...),
    state: str = Query("", description="org_id|context passed as state"),
):
    """Meta OAuth redirect for Instagram."""
    if not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing org_id in state")

    org_id, context = _parse_oauth_state(state)

    redirect_uri = f"{settings.API_BASE_URL}/api/social/instagram/callback"
    try:
        tokens = await instagram_service.authenticate(code, redirect_uri)
    except Exception as e:
        logger.error("Instagram OAuth failed: %s", e)
        return RedirectResponse(_oauth_redirect_url(context, "instagram", error=True))

    # Save account
    account_data = {
        "org_id": org_id,
        "platform": "instagram",
        "access_token": tokens["access_token"],
        "platform_user_id": tokens.get("user_id", ""),
        "is_active": True,
        "settings": {},
    }
    if tokens.get("expires_in"):
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
        account_data["token_expires_at"] = expires_at.isoformat()

    _social_db.table("social_accounts").insert(account_data).execute()

    return RedirectResponse(_oauth_redirect_url(context, "instagram"))


@router.get("/facebook/callback")
async def facebook_oauth_callback(
    code: str = Query(...),
    state: str = Query("", description="org_id|context passed as state"),
):
    """Meta OAuth redirect for Facebook Pages."""
    if not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing org_id in state")

    org_id, context = _parse_oauth_state(state)

    redirect_uri = f"{settings.API_BASE_URL}/api/social/facebook/callback"
    try:
        tokens = await facebook_service.authenticate(code, redirect_uri)
    except Exception as e:
        logger.error("Facebook OAuth failed: %s", e)
        return RedirectResponse(_oauth_redirect_url(context, "facebook", error=True))

    account_data = {
        "org_id": org_id,
        "platform": "facebook",
        "access_token": tokens["access_token"],
        "platform_page_id": tokens.get("page_id", ""),
        "platform_username": tokens.get("page_name", ""),
        "is_active": True,
        "settings": {},
    }
    _social_db.table("social_accounts").insert(account_data).execute()

    return RedirectResponse(_oauth_redirect_url(context, "facebook"))


@router.get("/tiktok/callback")
async def tiktok_oauth_callback(
    code: str = Query(...),
    state: str = Query("", description="org_id|context passed as state"),
):
    """TikTok OAuth redirect."""
    if not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing org_id in state")

    org_id, context = _parse_oauth_state(state)

    redirect_uri = f"{settings.API_BASE_URL}/api/social/tiktok/callback"
    try:
        tokens = await tiktok_service.authenticate(code, redirect_uri)
    except Exception as e:
        logger.error("TikTok OAuth failed: %s", e)
        return RedirectResponse(_oauth_redirect_url(context, "tiktok", error=True))

    account_data = {
        "org_id": org_id,
        "platform": "tiktok",
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "platform_user_id": tokens.get("open_id", ""),
        "is_active": True,
        "settings": {},
    }
    if tokens.get("expires_in"):
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
        account_data["token_expires_at"] = expires_at.isoformat()

    _social_db.table("social_accounts").insert(account_data).execute()

    return RedirectResponse(_oauth_redirect_url(context, "tiktok"))


@router.get("/google/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query("", description="org_id|context passed as state"),
):
    """Google OAuth redirect for Business Profile."""
    if not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing org_id in state")

    org_id, context = _parse_oauth_state(state)

    redirect_uri = f"{settings.API_BASE_URL}/api/social/google/callback"
    try:
        tokens = await google_business_service.authenticate(code, redirect_uri)
    except Exception as e:
        logger.error("Google OAuth failed: %s", e)
        return RedirectResponse(_oauth_redirect_url(context, "google_business", error=True))

    account_data = {
        "org_id": org_id,
        "platform": "google_business",
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "platform_page_id": tokens.get("location_name", ""),
        "platform_username": tokens.get("account_name", ""),
        "is_active": True,
        "settings": {},
    }
    if tokens.get("expires_in"):
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
        account_data["token_expires_at"] = expires_at.isoformat()

    _social_db.table("social_accounts").insert(account_data).execute()

    return RedirectResponse(_oauth_redirect_url(context, "google_business"))
