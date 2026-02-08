"""
Social Media Integrations

Unified interface for automating social media posts from FoodCartOS events:
- Instagram (via Meta Graph API)
- Facebook Pages (via Meta Graph API)
- TikTok (via Content Posting API)
- Google Business Profile (via Business Profile API)
"""

from app.services.social_media.base import (
    PostMedia,
    PostStatus,
    PostTrigger,
    PublishResult,
    SocialMediaService,
    SocialPlatform,
    SocialPost,
)
from app.services.social_media.instagram import instagram_service, InstagramService
from app.services.social_media.facebook import facebook_service, FacebookService
from app.services.social_media.tiktok import tiktok_service, TikTokService
from app.services.social_media.google_business import google_business_service, GoogleBusinessService
from app.services.social_media.content_generator import content_generator_service, ContentGeneratorService
from app.services.social_media.publisher import post_publisher_service, PostPublisherService

__all__ = [
    # Base classes
    "PostMedia",
    "PostStatus",
    "PostTrigger",
    "PublishResult",
    "SocialMediaService",
    "SocialPlatform",
    "SocialPost",
    # Platform services
    "instagram_service",
    "InstagramService",
    "facebook_service",
    "FacebookService",
    "tiktok_service",
    "TikTokService",
    "google_business_service",
    "GoogleBusinessService",
    # Content & publishing
    "content_generator_service",
    "ContentGeneratorService",
    "post_publisher_service",
    "PostPublisherService",
]
