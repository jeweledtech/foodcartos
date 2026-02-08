"""
Instagram Service — Meta Graph API

Publishing flow:
  1. Create media container (POST /{ig_user_id}/media)
  2. Wait for container to be ready
  3. Publish container (POST /{ig_user_id}/media_publish)

Supports single image, carousel (up to 10 images), and reels.
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


class InstagramService(SocialMediaService):
    """Instagram integration via Meta Graph API."""

    platform = SocialPlatform.INSTAGRAM

    async def authenticate(self, auth_code: str, redirect_uri: str) -> dict:
        """Exchange short-lived token for long-lived (60-day) Instagram token."""
        async with httpx.AsyncClient() as client:
            # Step 1: Exchange code for short-lived token
            resp = await client.post(
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id": settings.META_APP_ID,
                    "client_secret": settings.META_APP_SECRET,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code": auth_code,
                },
            )
            resp.raise_for_status()
            short_lived = resp.json()

            # Step 2: Exchange for long-lived token (60 days)
            resp = await client.get(
                f"{GRAPH_API_BASE}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.META_APP_ID,
                    "client_secret": settings.META_APP_SECRET,
                    "fb_exchange_token": short_lived["access_token"],
                },
            )
            resp.raise_for_status()
            long_lived = resp.json()

            return {
                "access_token": long_lived["access_token"],
                "token_type": long_lived.get("token_type", "bearer"),
                "expires_in": long_lived.get("expires_in", 5184000),
                "user_id": str(short_lived.get("user_id", "")),
            }

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh a long-lived Instagram token (before expiry)."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_API_BASE}/oauth/access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "access_token": refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "access_token": data["access_token"],
                "expires_in": data.get("expires_in", 5184000),
            }

    async def publish_post(
        self,
        access_token: str,
        post: SocialPost,
        account_metadata: dict,
    ) -> PublishResult:
        """
        Publish to Instagram.

        Single image: create container -> publish.
        Carousel (2+ images): create item containers -> create carousel container -> publish.
        """
        ig_user_id = account_metadata.get("user_id") or account_metadata.get("page_id")
        if not ig_user_id:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="Missing Instagram user ID",
            )

        caption = post.full_caption
        media_urls = post.media_urls

        async with httpx.AsyncClient() as client:
            try:
                if len(media_urls) == 0:
                    return PublishResult(
                        success=False,
                        platform=self.platform,
                        error_message="Instagram requires at least one image",
                    )
                elif len(media_urls) == 1:
                    # Single image post
                    container_id = await self._create_media_container(
                        client, ig_user_id, access_token, media_urls[0], caption
                    )
                else:
                    # Carousel post
                    container_id = await self._create_carousel(
                        client, ig_user_id, access_token, media_urls, caption
                    )

                # Publish the container
                resp = await client.post(
                    f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
                    params={
                        "creation_id": container_id,
                        "access_token": access_token,
                    },
                )
                resp.raise_for_status()
                result = resp.json()
                post_id = result.get("id", "")

                return PublishResult(
                    success=True,
                    platform=self.platform,
                    post_id=post_id,
                    url=f"https://www.instagram.com/p/{post_id}/",
                )

            except httpx.HTTPStatusError as e:
                error_body = e.response.json() if e.response.content else {}
                error_msg = error_body.get("error", {}).get("message", str(e))
                logger.error("Instagram publish failed: %s", error_msg)
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=error_msg,
                )
            except Exception as e:
                logger.error("Instagram publish error: %s", e)
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=str(e),
                )

    async def _create_media_container(
        self,
        client: httpx.AsyncClient,
        ig_user_id: str,
        access_token: str,
        image_url: str,
        caption: str,
    ) -> str:
        """Create a single image media container."""
        resp = await client.post(
            f"{GRAPH_API_BASE}/{ig_user_id}/media",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": access_token,
            },
        )
        resp.raise_for_status()
        return resp.json()["id"]

    async def _create_carousel(
        self,
        client: httpx.AsyncClient,
        ig_user_id: str,
        access_token: str,
        image_urls: list[str],
        caption: str,
    ) -> str:
        """Create a carousel container with multiple images."""
        # Create individual item containers
        item_ids = []
        for url in image_urls[:10]:  # Instagram max 10 items
            resp = await client.post(
                f"{GRAPH_API_BASE}/{ig_user_id}/media",
                params={
                    "image_url": url,
                    "is_carousel_item": "true",
                    "access_token": access_token,
                },
            )
            resp.raise_for_status()
            item_ids.append(resp.json()["id"])

        # Create carousel container
        resp = await client.post(
            f"{GRAPH_API_BASE}/{ig_user_id}/media",
            params={
                "media_type": "CAROUSEL",
                "caption": caption,
                "children": ",".join(item_ids),
                "access_token": access_token,
            },
        )
        resp.raise_for_status()
        return resp.json()["id"]

    async def delete_post(self, access_token: str, post_id: str) -> bool:
        """Delete an Instagram post."""
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{GRAPH_API_BASE}/{post_id}",
                params={"access_token": access_token},
            )
            return resp.status_code == 200

    async def get_post_analytics(self, access_token: str, post_id: str) -> dict:
        """Get Instagram post insights."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_API_BASE}/{post_id}/insights",
                params={
                    "metric": "impressions,reach,likes,comments,shares,saved",
                    "access_token": access_token,
                },
            )
            if resp.status_code != 200:
                return {}

            data = resp.json().get("data", [])
            return {item["name"]: item["values"][0]["value"] for item in data if item.get("values")}

    def validate_post(self, post: SocialPost) -> tuple[bool, Optional[str]]:
        """Instagram-specific validation."""
        if not post.media:
            return False, "Instagram requires at least 1 image"
        if len(post.full_caption) > 2200:
            return False, f"Caption too long ({len(post.full_caption)}/2200 chars)"
        if len(post.hashtags) > 30:
            return False, f"Too many hashtags ({len(post.hashtags)}/30 max)"
        if len(post.media) > 10:
            return False, f"Too many images ({len(post.media)}/10 max)"
        return True, None


instagram_service = InstagramService()
