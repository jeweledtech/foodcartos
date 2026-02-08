"""
Social Media Base Service

Provides a unified interface for all social media platform integrations.
Each platform (Instagram, Facebook, TikTok, Google Business) extends this base class.

Mirrors the delivery_platforms/base.py pattern.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SocialPlatform(str, Enum):
    """Supported social media platforms."""
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    GOOGLE_BUSINESS = "google_business"


class PostStatus(str, Enum):
    """Post lifecycle status."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    REJECTED = "rejected"


class PostTrigger(str, Enum):
    """What triggered the post creation."""
    QUALITY_CHECK = "quality_check"
    LOCATION_ARRIVAL = "location_arrival"
    MILESTONE = "milestone"
    MANUAL = "manual"
    NEW_LOCATION = "new_location"
    ORDER_VOLUME = "order_volume"


@dataclass
class PostMedia:
    """A single media attachment for a social post."""
    url: str
    media_type: str = "image"  # "image" or "video"
    alt_text: str = ""


@dataclass
class SocialPost:
    """Unified social post format across all platforms."""
    # Content
    caption: str = ""
    media: list[PostMedia] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)

    # Trigger context
    trigger_type: PostTrigger = PostTrigger.MANUAL
    trigger_entity_id: Optional[str] = None

    # Status
    status: PostStatus = PostStatus.DRAFT
    target_platforms: list[SocialPlatform] = field(default_factory=list)
    platform_post_ids: dict[str, str] = field(default_factory=dict)

    # Organization
    org_id: str = ""

    # Identifiers
    id: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    scheduled_for: Optional[datetime] = None

    @property
    def full_caption(self) -> str:
        """Caption with hashtags appended."""
        if not self.hashtags:
            return self.caption
        tags = " ".join(f"#{tag.lstrip('#')}" for tag in self.hashtags)
        return f"{self.caption}\n\n{tags}"

    @property
    def media_urls(self) -> list[str]:
        """Flat list of media URLs."""
        return [m.url for m in self.media]

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "caption": self.caption,
            "media_urls": self.media_urls,
            "hashtags": self.hashtags,
            "trigger_type": self.trigger_type.value,
            "trigger_entity_id": self.trigger_entity_id,
            "status": self.status.value,
            "target_platforms": [p.value for p in self.target_platforms],
            "platform_post_ids": self.platform_post_ids,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
        }


@dataclass
class PublishResult:
    """Result of publishing to a single platform."""
    success: bool
    platform: SocialPlatform
    post_id: str = ""
    error_message: str = ""
    url: str = ""


class SocialMediaService(ABC):
    """
    Abstract base class for social media platform integrations.

    Each platform (Instagram, Facebook, TikTok, Google Business)
    implements this interface.
    """

    platform: SocialPlatform

    @abstractmethod
    async def authenticate(self, auth_code: str, redirect_uri: str) -> dict:
        """
        Exchange OAuth authorization code for access tokens.

        Returns dict with access_token, refresh_token, expires_in, etc.
        """
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> dict:
        """
        Refresh an expired access token.

        Returns dict with new access_token and expiry.
        """
        pass

    @abstractmethod
    async def publish_post(
        self,
        access_token: str,
        post: SocialPost,
        account_metadata: dict,
    ) -> PublishResult:
        """
        Publish a post to the platform.

        account_metadata contains platform-specific IDs (page_id, etc.)
        """
        pass

    @abstractmethod
    async def delete_post(self, access_token: str, post_id: str) -> bool:
        """Delete a published post from the platform."""
        pass

    @abstractmethod
    async def get_post_analytics(self, access_token: str, post_id: str) -> dict:
        """Fetch engagement analytics for a published post."""
        pass

    def validate_post(self, post: SocialPost) -> tuple[bool, Optional[str]]:
        """
        Validate a post meets platform requirements.

        Returns (is_valid, error_message).
        Override in subclasses for platform-specific rules.
        """
        if not post.caption and not post.media:
            return False, "Post must have either a caption or media"
        return True, None
