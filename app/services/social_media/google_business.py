"""
Google Business Profile Service — Business Profile API

Creates "Local Posts" that appear on Google Maps and Search results.
This is the most valuable platform for a food cart — when someone
searches "hot dogs near me", the local post shows up right in the listing.

Post types: UPDATE (What's New), OFFER, EVENT
"""

import logging
from typing import Optional

import httpx

from app.config import settings
from app.services.social_media.base import (
    PublishResult,
    SocialMediaService,
    SocialPlatform,
    SocialPost,
)

logger = logging.getLogger(__name__)

GOOGLE_API_BASE = "https://mybusiness.googleapis.com/v4"
GOOGLE_OAUTH_BASE = "https://oauth2.googleapis.com"


class GoogleBusinessService(SocialMediaService):
    """Google Business Profile integration for local posts."""

    platform = SocialPlatform.GOOGLE_BUSINESS

    async def authenticate(self, auth_code: str, redirect_uri: str) -> dict:
        """Exchange Google OAuth code for tokens."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GOOGLE_OAUTH_BASE}/token",
                data={
                    "code": auth_code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # Get the business account/location info
            account_info = await self._get_account_info(data["access_token"], client)

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "expires_in": data.get("expires_in", 3600),
                "account_name": account_info.get("account_name", ""),
                "location_name": account_info.get("location_name", ""),
            }

    async def _get_account_info(self, access_token: str, client: httpx.AsyncClient) -> dict:
        """Fetch the first business account and location."""
        headers = {"Authorization": f"Bearer {access_token}"}

        # Get accounts
        resp = await client.get(
            f"{GOOGLE_API_BASE}/accounts",
            headers=headers,
        )
        if resp.status_code != 200:
            return {}

        accounts = resp.json().get("accounts", [])
        if not accounts:
            return {}

        account = accounts[0]
        account_name = account.get("name", "")

        # Get locations for this account
        resp = await client.get(
            f"{GOOGLE_API_BASE}/{account_name}/locations",
            headers=headers,
        )
        if resp.status_code != 200:
            return {"account_name": account_name}

        locations = resp.json().get("locations", [])
        location_name = locations[0].get("name", "") if locations else ""

        return {
            "account_name": account_name,
            "location_name": location_name,
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh Google access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GOOGLE_OAUTH_BASE}/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "access_token": data["access_token"],
                "expires_in": data.get("expires_in", 3600),
            }

    async def publish_post(
        self,
        access_token: str,
        post: SocialPost,
        account_metadata: dict,
    ) -> PublishResult:
        """
        Create a local post on Google Business Profile.

        Creates an "UPDATE" (What's New) type post by default.
        """
        # location_name is in format "accounts/{id}/locations/{id}"
        page_id = account_metadata.get("page_id", "")
        if not page_id:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="Missing Google Business location name",
            )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Build local post payload
        local_post = {
            "languageCode": "en",
            "summary": post.full_caption[:1500],  # Google limit
            "topicType": "STANDARD",
        }

        # Add media if available
        if post.media_urls:
            local_post["media"] = [
                {
                    "mediaFormat": "PHOTO",
                    "sourceUrl": post.media_urls[0],  # Google supports 1 image
                }
            ]

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{GOOGLE_API_BASE}/{page_id}/localPosts",
                    headers=headers,
                    json=local_post,
                )
                resp.raise_for_status()
                result = resp.json()
                post_name = result.get("name", "")

                return PublishResult(
                    success=True,
                    platform=self.platform,
                    post_id=post_name,
                )

            except httpx.HTTPStatusError as e:
                error_body = e.response.json() if e.response.content else {}
                error_msg = error_body.get("error", {}).get("message", str(e))
                logger.error("Google Business publish failed: %s", error_msg)
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=error_msg,
                )
            except Exception as e:
                logger.error("Google Business publish error: %s", e)
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=str(e),
                )

    async def delete_post(self, access_token: str, post_id: str) -> bool:
        """Delete a Google Business local post."""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{GOOGLE_API_BASE}/{post_id}",
                headers=headers,
            )
            return resp.status_code == 200

    async def get_post_analytics(self, access_token: str, post_id: str) -> dict:
        """Get local post insights (views, clicks)."""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GOOGLE_API_BASE}/{post_id}",
                headers=headers,
            )
            if resp.status_code != 200:
                return {}

            data = resp.json()
            search_url = data.get("searchUrl", "")
            return {
                "search_url": search_url,
                "state": data.get("state", ""),
            }

    def validate_post(self, post: SocialPost) -> tuple[bool, Optional[str]]:
        """Google Business-specific validation."""
        if not post.caption and not post.media:
            return False, "Post must have either text or an image"
        if len(post.full_caption) > 1500:
            return False, f"Summary too long ({len(post.full_caption)}/1500 chars)"
        return True, None


google_business_service = GoogleBusinessService()
