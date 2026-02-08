"""
Social Media Content Generator

Generates social media post drafts from FoodCartOS events:
- Quality check approvals (daily authentic content with real photos)
- Location arrivals (great for Google Business Profile visibility)
- Milestones (customer count, record day, weekly total)
- New location announcements

Uses org-customizable templates with sensible defaults.
"""

from collections import defaultdict
from typing import Optional

from app.services.social_media.base import (
    PostMedia,
    PostTrigger,
    SocialPlatform,
    SocialPost,
    PostStatus,
)
from app.services.supabase import SupabaseService


# Default templates — used when no org-specific template exists.
# These work out of the box with zero configuration.
DEFAULT_TEMPLATES = {
    PostTrigger.QUALITY_CHECK: {
        "caption": "Fresh {check_type} ready at {location}!",
        "hashtags": ["foodcart", "freshfood", "streetfood", "madewithlove"],
    },
    PostTrigger.LOCATION_ARRIVAL: {
        "caption": "We're set up at {location}! Come find us today",
        "hashtags": ["foodcart", "streetfood", "lunchtime", "opentoday"],
    },
    PostTrigger.MILESTONE: {
        "caption": "{count} customers served this {period}! Thank you {city}!",
        "hashtags": ["milestone", "thankyou", "foodcart", "community"],
    },
    PostTrigger.NEW_LOCATION: {
        "caption": "NEW SPOT! Find us at {location} every {day}!",
        "hashtags": ["newlocation", "foodcart", "grandopening", "streetfood"],
    },
    PostTrigger.ORDER_VOLUME: {
        "caption": "Busy day at {location}! {count} orders and counting",
        "hashtags": ["busyday", "foodcart", "popular", "streetfood"],
    },
}


class ContentGeneratorService(SupabaseService):
    """
    Generates social media post drafts from FoodCartOS events.

    Reads org-customizable templates from social_templates table,
    falling back to hardcoded defaults.
    """

    async def _get_template(self, org_id: str, trigger_type: PostTrigger) -> dict:
        """
        Get the best template for this org and trigger type.

        Checks org-specific templates first, then falls back to defaults.
        """
        result = (
            self.table("social_templates")
            .select("*")
            .eq("org_id", org_id)
            .eq("trigger_type", trigger_type.value)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

        if result.data:
            row = result.data[0]
            return {
                "caption": row["caption_template"],
                "hashtags": row.get("default_hashtags", []),
            }

        return DEFAULT_TEMPLATES.get(trigger_type, DEFAULT_TEMPLATES[PostTrigger.QUALITY_CHECK])

    def _render_template(self, template_caption: str, context: dict) -> str:
        """
        Render a template string with context variables.

        Uses defaultdict so missing variables produce empty string instead of KeyError.
        """
        safe_context = defaultdict(str, context)
        return template_caption.format_map(safe_context)

    async def _get_active_platforms(self, org_id: str) -> list[SocialPlatform]:
        """Get all active social platforms for this org."""
        result = (
            self.table("social_accounts")
            .select("platform")
            .eq("org_id", org_id)
            .eq("is_active", True)
            .execute()
        )
        return [SocialPlatform(row["platform"]) for row in result.data]

    async def generate_from_quality_check(
        self,
        quality_check: dict,
        org_id: str,
        location_name: Optional[str] = None,
    ) -> SocialPost:
        """
        Generate a post from a quality check approval.

        This is the best trigger — authentic daily content with real photos
        that show the food being prepared.
        """
        template = await self._get_template(org_id, PostTrigger.QUALITY_CHECK)
        target_platforms = await self._get_active_platforms(org_id)

        # Build template context from quality check data
        context = {
            "check_type": (quality_check.get("check_type", "prep") or "prep").replace("_", " "),
            "location": location_name or "our cart",
        }

        caption = self._render_template(template["caption"], context)

        # Use quality check photo as post media
        media = []
        photo_url = quality_check.get("photo_url")
        if photo_url:
            media.append(PostMedia(
                url=photo_url,
                media_type="image",
                alt_text=f"Quality check: {context['check_type']}",
            ))

        return SocialPost(
            caption=caption,
            media=media,
            hashtags=template["hashtags"],
            trigger_type=PostTrigger.QUALITY_CHECK,
            trigger_entity_id=quality_check.get("id"),
            status=PostStatus.DRAFT,
            target_platforms=target_platforms,
            org_id=org_id,
        )

    async def generate_from_location_arrival(
        self,
        cart: dict,
        location: dict,
        org_id: str,
    ) -> SocialPost:
        """
        Generate a post when a cart arrives at a location.

        Particularly valuable for Google Business Profile — shows up
        directly on Google Maps/Search.
        """
        template = await self._get_template(org_id, PostTrigger.LOCATION_ARRIVAL)
        target_platforms = await self._get_active_platforms(org_id)

        context = {
            "location": location.get("name", "our spot"),
            "address": location.get("address", ""),
            "cart_name": cart.get("name", "our cart"),
        }

        caption = self._render_template(template["caption"], context)

        return SocialPost(
            caption=caption,
            hashtags=template["hashtags"],
            trigger_type=PostTrigger.LOCATION_ARRIVAL,
            trigger_entity_id=cart.get("id"),
            status=PostStatus.DRAFT,
            target_platforms=target_platforms,
            org_id=org_id,
        )

    async def generate_from_milestone(
        self,
        milestone_type: str,
        data: dict,
        org_id: str,
    ) -> SocialPost:
        """
        Generate a post for business milestones.

        Types: customer_count, record_day, weekly_total
        """
        template = await self._get_template(org_id, PostTrigger.MILESTONE)
        target_platforms = await self._get_active_platforms(org_id)

        context = {
            "count": str(data.get("count", "")),
            "period": data.get("period", "week"),
            "city": data.get("city", "our community"),
            "milestone_type": milestone_type,
        }

        caption = self._render_template(template["caption"], context)

        return SocialPost(
            caption=caption,
            hashtags=template["hashtags"],
            trigger_type=PostTrigger.MILESTONE,
            status=PostStatus.DRAFT,
            target_platforms=target_platforms,
            org_id=org_id,
        )

    async def generate_from_new_location(
        self,
        location: dict,
        org_id: str,
    ) -> SocialPost:
        """
        Generate a post for a new location announcement.

        First time at a new spot — exciting content.
        """
        template = await self._get_template(org_id, PostTrigger.NEW_LOCATION)
        target_platforms = await self._get_active_platforms(org_id)

        context = {
            "location": location.get("name", "a new spot"),
            "address": location.get("address", ""),
            "day": location.get("day", ""),
        }

        caption = self._render_template(template["caption"], context)

        return SocialPost(
            caption=caption,
            hashtags=template["hashtags"],
            trigger_type=PostTrigger.NEW_LOCATION,
            trigger_entity_id=location.get("id"),
            status=PostStatus.DRAFT,
            target_platforms=target_platforms,
            org_id=org_id,
        )


# Default service instance (uses service role for admin operations)
content_generator_service = ContentGeneratorService(use_admin=True)
