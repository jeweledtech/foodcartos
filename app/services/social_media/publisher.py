"""
Social Media Post Publisher

Manages the full post lifecycle:
  1. Save draft to database
  2. Check auto-approve settings per trigger type
  3. Either publish immediately or send SMS approval to owner
  4. Publish to all connected platforms on approval
  5. Track results and errors

Uses Twilio for SMS approval notifications.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.services.social_media.base import (
    PostStatus,
    PublishResult,
    SocialPlatform,
    SocialPost,
)
from app.services.supabase import SupabaseService

logger = logging.getLogger(__name__)


class PostPublisherService(SupabaseService):
    """
    Manages post lifecycle: create -> approve -> publish.

    Integrates with platform services for actual publishing
    and Twilio for SMS approval flow.
    """

    def _get_platform_service(self, platform: SocialPlatform):
        """Get the service instance for a given platform."""
        # Lazy import to avoid circular dependencies
        from app.services.social_media import (
            instagram_service,
            facebook_service,
            tiktok_service,
            google_business_service,
        )

        services = {
            SocialPlatform.INSTAGRAM: instagram_service,
            SocialPlatform.FACEBOOK: facebook_service,
            SocialPlatform.TIKTOK: tiktok_service,
            SocialPlatform.GOOGLE_BUSINESS: google_business_service,
        }
        return services.get(platform)

    async def _save_post(self, post: SocialPost) -> Optional[dict]:
        """Save a post draft to the database."""
        data = {
            "org_id": post.org_id,
            **post.to_dict(),
        }
        result = self.table("social_posts").insert(data).execute()
        return result.data[0] if result.data else None

    async def _update_post_status(
        self,
        post_id: str,
        status: PostStatus,
        **extra_fields,
    ) -> Optional[dict]:
        """Update a post's status and optional extra fields."""
        data = {"status": status.value, **extra_fields}
        result = (
            self.table("social_posts")
            .update(data)
            .eq("id", post_id)
            .execute()
        )
        return result.data[0] if result.data else None

    async def get_active_accounts(self, org_id: str) -> list[dict]:
        """Get all active social accounts for an org."""
        result = (
            self.table("social_accounts")
            .select("*")
            .eq("org_id", org_id)
            .eq("is_active", True)
            .execute()
        )
        return result.data

    async def handle_new_post(
        self,
        post: SocialPost,
        org_id: str,
        owner_phone: Optional[str] = None,
    ) -> dict:
        """
        Handle a newly generated post.

        1. Save draft to social_posts table
        2. Check auto-approve settings for this trigger type
        3. Either publish immediately or send SMS approval
        """
        post.org_id = org_id

        # Save to database
        saved = await self._save_post(post)
        if not saved:
            logger.error("Failed to save social post for org %s", org_id)
            return {"status": "error", "message": "Failed to save post"}

        post_id = saved["id"]

        # Check auto-approve settings
        accounts = await self.get_active_accounts(org_id)
        auto_approve_key = f"auto_approve_{post.trigger_type.value}"
        should_auto = any(
            a.get("settings", {}).get(auto_approve_key, False)
            for a in accounts
        )

        if should_auto:
            # Publish immediately
            results = await self.publish_post(post_id)
            return {"status": "published", "post_id": post_id, "results": results}
        else:
            # Send SMS approval to owner
            if owner_phone:
                await self._send_approval_sms(post, post_id, owner_phone)
            await self._update_post_status(
                post_id,
                PostStatus.PENDING_APPROVAL,
                approval_sent_at=datetime.now(timezone.utc).isoformat(),
                approval_sent_to=owner_phone,
            )
            return {"status": "pending_approval", "post_id": post_id}

    async def _send_approval_sms(
        self,
        post: SocialPost,
        post_id: str,
        phone: str,
    ) -> None:
        """Send SMS with approve/edit/skip links via Twilio."""
        base_url = settings.API_BASE_URL

        # Truncate caption for SMS preview
        preview = post.caption[:80] + "..." if len(post.caption) > 80 else post.caption
        media_count = len(post.media)

        message = (
            f"New post ready:\n"
            f'"{preview}"\n'
            f"{'📸 ' + str(media_count) + ' photo(s)' if media_count else ''}\n\n"
            f"Approve: {base_url}/api/social/approve/{post_id}\n"
            f"Edit: {base_url}/api/social/edit/{post_id}\n"
            f"Skip: {base_url}/api/social/skip/{post_id}"
        )

        try:
            from twilio.rest import Client as TwilioClient

            client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone,
            )
            logger.info("Approval SMS sent for post %s to %s", post_id, phone)
        except Exception as e:
            logger.error("Failed to send approval SMS for post %s: %s", post_id, e)

    async def publish_post(self, post_id: str) -> list[dict]:
        """
        Publish a post to all target platforms.

        Iterates over target_platforms, gets the appropriate service,
        and calls publish_post() on each.
        """
        # Fetch the post
        result = self.table("social_posts").select("*").eq("id", post_id).execute()
        if not result.data:
            return [{"error": "Post not found"}]

        post_data = result.data[0]
        org_id = post_data["org_id"]

        # Mark as publishing
        await self._update_post_status(post_id, PostStatus.PUBLISHING)

        # Get accounts for this org
        accounts = await self.get_active_accounts(org_id)
        accounts_by_platform = {a["platform"]: a for a in accounts}

        # Build SocialPost from DB data
        post = SocialPost(
            id=post_id,
            caption=post_data["caption"],
            hashtags=post_data.get("hashtags", []),
            org_id=org_id,
        )

        results = []
        platform_post_ids = dict(post_data.get("platform_post_ids", {}))

        for platform_str in post_data.get("target_platforms", []):
            platform = SocialPlatform(platform_str)
            service = self._get_platform_service(platform)
            account = accounts_by_platform.get(platform_str)

            if not service or not account:
                results.append({
                    "platform": platform_str,
                    "success": False,
                    "error": f"No active account for {platform_str}",
                })
                continue

            # Validate before publishing
            valid, error = service.validate_post(post)
            if not valid:
                results.append({
                    "platform": platform_str,
                    "success": False,
                    "error": error,
                })
                continue

            try:
                publish_result: PublishResult = await service.publish_post(
                    access_token=account["access_token"],
                    post=post,
                    account_metadata={
                        "page_id": account.get("platform_page_id"),
                        "user_id": account.get("platform_user_id"),
                        "username": account.get("platform_username"),
                    },
                )
                if publish_result.success:
                    platform_post_ids[platform_str] = publish_result.post_id

                results.append({
                    "platform": platform_str,
                    "success": publish_result.success,
                    "post_id": publish_result.post_id,
                    "url": publish_result.url,
                    "error": publish_result.error_message or None,
                })
            except Exception as e:
                logger.error("Failed to publish to %s: %s", platform_str, e)
                results.append({
                    "platform": platform_str,
                    "success": False,
                    "error": str(e),
                })

        # Update post with results
        any_success = any(r.get("success") for r in results)
        all_failed = all(not r.get("success") for r in results)

        if any_success:
            now = datetime.now(timezone.utc).isoformat()
            await self._update_post_status(
                post_id,
                PostStatus.PUBLISHED,
                platform_post_ids=platform_post_ids,
                published_at=now,
            )
        elif all_failed and results:
            error_messages = "; ".join(
                f"{r['platform']}: {r.get('error', 'unknown')}"
                for r in results if not r.get("success")
            )
            await self._update_post_status(
                post_id,
                PostStatus.FAILED,
                error_message=error_messages,
            )

        return results

    async def approve_post(self, post_id: str, approved_by: str = "") -> dict:
        """Approve a pending post and publish it."""
        now = datetime.now(timezone.utc).isoformat()
        await self._update_post_status(
            post_id,
            PostStatus.APPROVED,
            approved_at=now,
            approved_by=approved_by,
        )
        results = await self.publish_post(post_id)
        return {"status": "published", "post_id": post_id, "results": results}

    async def reject_post(self, post_id: str) -> dict:
        """Reject/skip a pending post."""
        now = datetime.now(timezone.utc).isoformat()
        await self._update_post_status(post_id, PostStatus.REJECTED, rejected_at=now)
        return {"status": "rejected", "post_id": post_id}

    async def get_post(self, post_id: str) -> Optional[dict]:
        """Get a single post by ID."""
        result = self.table("social_posts").select("*").eq("id", post_id).execute()
        return result.data[0] if result.data else None

    async def list_posts(
        self,
        org_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """List posts for an org, optionally filtered by status."""
        query = self.table("social_posts").select("*").eq("org_id", org_id)
        if status:
            query = query.eq("status", status)
        result = query.order("created_at", desc=True).limit(limit).execute()
        return result.data

    async def delete_post(self, post_id: str) -> bool:
        """Delete a post from the database."""
        result = (
            self.table("social_posts")
            .delete()
            .eq("id", post_id)
            .execute()
        )
        return bool(result.data)


# Default service instance
post_publisher_service = PostPublisherService(use_admin=True)
