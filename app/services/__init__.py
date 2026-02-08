"""
FoodCartOS Services

Business logic and database operations.
"""

from app.services.supabase import (
    supabase_client,
    get_supabase,
    get_supabase_admin,
    SupabaseService,
    OrganizationService,
    UserService,
    LocationService,
    CartService,
    TransactionService,
    QualityCheckService,
    OrderService,
    organization_service,
    user_service,
    location_service,
    cart_service,
    transaction_service,
    quality_check_service,
    order_service,
)
from app.services.auth import auth_service, AuthService
from app.services.social_media import (
    content_generator_service,
    post_publisher_service,
    instagram_service,
    facebook_service,
    tiktok_service,
    google_business_service,
)

__all__ = [
    "auth_service",
    "AuthService",
    "supabase_client",
    "get_supabase",
    "get_supabase_admin",
    "SupabaseService",
    "OrganizationService",
    "UserService",
    "LocationService",
    "CartService",
    "TransactionService",
    "QualityCheckService",
    "OrderService",
    "organization_service",
    "user_service",
    "location_service",
    "cart_service",
    "transaction_service",
    "quality_check_service",
    "order_service",
    # Social media
    "content_generator_service",
    "post_publisher_service",
    "instagram_service",
    "facebook_service",
    "tiktok_service",
    "google_business_service",
]
