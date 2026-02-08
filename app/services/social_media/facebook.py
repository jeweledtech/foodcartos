"""
Facebook Pages Service — Meta Graph API

Posts to Facebook Pages (not personal profiles).
Shares the same Meta app as Instagram but uses Page access tokens.

Publishing flow:
  - Photo post: POST /{page_id}/photos
  - Text/link post: POST /{page_id}/feed
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

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class FacebookService(SocialMediaService):
    """Facebook Pages integration via Meta Graph API."""

    platform = SocialPlatform.FACEBOOK

    async def authenticate(self, auth_code: str, redirect_uri: str) -> dict:
        """
        Exchange code for user token, then get Page access token.

        Facebook OAuth returns a user token; we exchange it for a
        long-lived Page token that doesn't expire.
        """
        async with httpx.AsyncClient() as client:
            # Step 1: Exchange code for user access token
            resp = await client.get(
                f"{GRAPH_API_BASE}/oauth/access_token",
                params={
                    "client_id": settings.META_APP_ID,
                    "client_secret": settings.META_APP_SECRET,
                    "redirect_uri": redirect_uri,
                    "code": auth_code,
                },
            )
            resp.raise_for_status()
            user_token = resp.json()["access_token"]

            # Step 2: Exchange for long-lived user token
            resp = await client.get(
                f"{GRAPH_API_BASE}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.META_APP_ID,
                    "client_secret": settings.META_APP_SECRET,
                    "fb_exchange_token": user_token,
                },
            )
            resp.raise_for_status()
            long_lived_user = resp.json()

            # Step 3: Get Page access token (long-lived, doesn't expire)
            resp = await client.get(
                f"{GRAPH_API_BASE}/me/accounts",
                params={"access_token": long_lived_user["access_token"]},
            )
            resp.raise_for_status()
            pages = resp.json().get("data", [])

            if not pages:
                return {
                    "access_token": long_lived_user["access_token"],
                    "error": "No Facebook Pages found",
                }

            # Use first page (most food cart owners have one page)
            page = pages[0]
            return {
                "access_token": page["access_token"],
                "page_id": page["id"],
                "page_name": page.get("name", ""),
                "expires_in": None,  # Page tokens don't expire
            }

    async def refresh_token(self, refresh_token: str) -> dict:
        """
        Facebook Page tokens don't expire — no refresh needed.

        Returns the same token.
        """
        return {"access_token": refresh_token, "expires_in": None}

    async def publish_post(
        self,
        access_token: str,
        post: SocialPost,
        account_metadata: dict,
    ) -> PublishResult:
        """
        Publish to a Facebook Page.

        Uses /photos for image posts, /feed for text-only.
        """
        page_id = account_metadata.get("page_id")
        if not page_id:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="Missing Facebook Page ID",
            )

        caption = post.full_caption
        media_urls = post.media_urls

        async with httpx.AsyncClient() as client:
            try:
                if media_urls:
                    # Photo post (first image)
                    resp = await client.post(
                        f"{GRAPH_API_BASE}/{page_id}/photos",
                        params={
                            "url": media_urls[0],
                            "message": caption,
                            "access_token": access_token,
                        },
                    )
                else:
                    # Text-only post
                    resp = await client.post(
                        f"{GRAPH_API_BASE}/{page_id}/feed",
                        params={
                            "message": caption,
                            "access_token": access_token,
                        },
                    )

                resp.raise_for_status()
                result = resp.json()
                post_id = result.get("post_id") or result.get("id", "")

                return PublishResult(
                    success=True,
                    platform=self.platform,
                    post_id=post_id,
                    url=f"https://www.facebook.com/{post_id}",
                )

            except httpx.HTTPStatusError as e:
                error_body = e.response.json() if e.response.content else {}
                error_msg = error_body.get("error", {}).get("message", str(e))
                logger.error("Facebook publish failed: %s", error_msg)
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=error_msg,
                )
            except Exception as e:
                logger.error("Facebook publish error: %s", e)
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=str(e),
                )

    async def delete_post(self, access_token: str, post_id: str) -> bool:
        """Delete a Facebook post."""
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{GRAPH_API_BASE}/{post_id}",
                params={"access_token": access_token},
            )
            return resp.status_code == 200

    async def get_post_analytics(self, access_token: str, post_id: str) -> dict:
        """Get Facebook post insights."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_API_BASE}/{post_id}",
                params={
                    "fields": "likes.summary(true),comments.summary(true),shares",
                    "access_token": access_token,
                },
            )
            if resp.status_code != 200:
                return {}

            data = resp.json()
            return {
                "likes": data.get("likes", {}).get("summary", {}).get("total_count", 0),
                "comments": data.get("comments", {}).get("summary", {}).get("total_count", 0),
                "shares": data.get("shares", {}).get("count", 0),
            }

    def validate_post(self, post: SocialPost) -> tuple[bool, Optional[str]]:
        """Facebook-specific validation — very permissive limits."""
        if not post.caption and not post.media:
            return False, "Post must have either text or an image"
        if len(post.full_caption) > 63206:
            return False, f"Caption too long ({len(post.full_caption)}/63206 chars)"
        return True, None


facebook_service = FacebookService()
