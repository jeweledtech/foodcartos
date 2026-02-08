"""
TikTok Service — Content Posting API

TikTok is video-first but supports photo slideshows.
For FoodCartOS v1, quality check photos are posted as photo slideshows.

Publishing flow:
  1. Initialize upload (POST /v2/post/publish/creator_info/query/)
  2. Upload media
  3. Create post (POST /v2/post/publish/video/init/ or photo/init/)
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

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokService(SocialMediaService):
    """TikTok integration via Content Posting API."""

    platform = SocialPlatform.TIKTOK

    async def authenticate(self, auth_code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for TikTok access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{TIKTOK_API_BASE}/oauth/token/",
                data={
                    "client_key": settings.TIKTOK_CLIENT_KEY,
                    "client_secret": settings.TIKTOK_CLIENT_SECRET,
                    "code": auth_code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "expires_in": data.get("expires_in", 86400),
                "open_id": data.get("open_id", ""),
            }

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh TikTok access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{TIKTOK_API_BASE}/oauth/token/",
                data={
                    "client_key": settings.TIKTOK_CLIENT_KEY,
                    "client_secret": settings.TIKTOK_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", refresh_token),
                "expires_in": data.get("expires_in", 86400),
            }

    async def publish_post(
        self,
        access_token: str,
        post: SocialPost,
        account_metadata: dict,
    ) -> PublishResult:
        """
        Publish to TikTok as a photo slideshow.

        For v1, we use photo mode for quality check images.
        Video support can be added later.
        """
        media_urls = post.media_urls
        if not media_urls:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="TikTok requires at least one image or video",
            )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            try:
                # Use photo post endpoint for images
                payload = {
                    "post_info": {
                        "title": post.caption[:150],  # TikTok title limit
                        "privacy_level": "PUBLIC_TO_EVERYONE",
                        "disable_comment": False,
                        "auto_add_music": True,
                    },
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "photo_cover_index": 0,
                        "photo_images": media_urls[:35],  # TikTok photo limit
                    },
                }

                resp = await client.post(
                    f"{TIKTOK_API_BASE}/post/publish/content/init/",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                result = resp.json()

                publish_id = result.get("data", {}).get("publish_id", "")

                return PublishResult(
                    success=True,
                    platform=self.platform,
                    post_id=publish_id,
                )

            except httpx.HTTPStatusError as e:
                error_body = e.response.json() if e.response.content else {}
                error_msg = error_body.get("error", {}).get("message", str(e))
                logger.error("TikTok publish failed: %s", error_msg)
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=error_msg,
                )
            except Exception as e:
                logger.error("TikTok publish error: %s", e)
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=str(e),
                )

    async def delete_post(self, access_token: str, post_id: str) -> bool:
        """TikTok doesn't support programmatic post deletion via API."""
        logger.warning("TikTok does not support programmatic post deletion")
        return False

    async def get_post_analytics(self, access_token: str, post_id: str) -> dict:
        """Get TikTok video/photo insights."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{TIKTOK_API_BASE}/video/query/",
                headers=headers,
                json={"filters": {"video_ids": [post_id]}},
            )
            if resp.status_code != 200:
                return {}

            videos = resp.json().get("data", {}).get("videos", [])
            if not videos:
                return {}

            video = videos[0]
            return {
                "views": video.get("view_count", 0),
                "likes": video.get("like_count", 0),
                "comments": video.get("comment_count", 0),
                "shares": video.get("share_count", 0),
            }

    def validate_post(self, post: SocialPost) -> tuple[bool, Optional[str]]:
        """TikTok-specific validation."""
        if not post.media:
            return False, "TikTok requires at least 1 image or video"
        if len(post.caption) > 2200:
            return False, f"Caption too long ({len(post.caption)}/2200 chars)"
        if len(post.media) > 35:
            return False, f"Too many images ({len(post.media)}/35 max)"
        return True, None


tiktok_service = TikTokService()
