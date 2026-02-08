#!/usr/bin/env python3
"""
Seed Script: EatFireCraft Demo Data

Creates Poncho's EatFireCraft organization with:
- Organization record
- Owner user (Poncho)
- 3 carts
- Key locations (Courthouse, DMV, Sheriff's Office, Downtown)
- Sample transactions showing the location patterns
- Sample quality checks

Run with: python scripts/seed_eatfirecraft.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.supabase import (
    OrganizationService,
    UserService,
    LocationService,
    CartService,
    TransactionService,
    QualityCheckService,
)

# Create admin instances that bypass RLS for seeding
organization_service = OrganizationService(use_admin=True)
user_service = UserService(use_admin=True)
location_service = LocationService(use_admin=True)
cart_service = CartService(use_admin=True)
transaction_service = TransactionService(use_admin=True)
quality_check_service = QualityCheckService(use_admin=True)


async def seed_eatfirecraft():
    """Seed EatFireCraft demo data."""
    print("🌭 Seeding EatFireCraft data...")

    # ===========================================
    # 1. Create Organization
    # ===========================================
    print("\n📦 Creating organization...")

    org = await organization_service.create(
        name="EatFireCraft",
        slug="eatfirecraft",
        settings={
            "brand_name": "EatFireCraft",
            "tagline": "Premium Dirty Water Hot Dogs",
            "quality_checks_required": ["dirty_water", "garlic_butter", "cart_display"],
            "check_deadline_minutes": 30,
            "timezone": "America/Los_Angeles"
        }
    )
    org_id = org["id"]
    print(f"   ✅ Created organization: {org['name']} ({org_id})")

    # ===========================================
    # 2. Create Users
    # ===========================================
    print("\n👥 Creating users...")

    poncho = await user_service.create(
        org_id=org_id,
        email="poncho@eatfirecraft.com",
        name="Poncho",
        role="owner",
        phone="+15551234567"
    )
    print(f"   ✅ Created owner: {poncho['name']}")

    brother = await user_service.create(
        org_id=org_id,
        email="brother@eatfirecraft.com",
        name="Brother-in-law",
        role="operator",
        phone="+15559876543"
    )
    print(f"   ✅ Created operator: {brother['name']}")

    new_hire = await user_service.create(
        org_id=org_id,
        email="newhire@eatfirecraft.com",
        name="New Hire",
        role="employee",
        phone="+15555555555"
    )
    print(f"   ✅ Created employee: {new_hire['name']}")

    # ===========================================
    # 3. Create Locations
    # ===========================================
    print("\n📍 Creating locations...")

    courthouse = await location_service.create(
        org_id=org_id,
        name="Courthouse",
        latitude=38.3566,
        longitude=-121.9877,
        address="123 Main St, Vacaville, CA",
        location_type="courthouse",
        notes="Jury duty days are Thursday - 74% higher revenue! Federal/state workers."
    )
    print(f"   ✅ Created location: {courthouse['name']}")

    dmv = await location_service.create(
        org_id=org_id,
        name="DMV",
        latitude=38.3600,
        longitude=-121.9800,
        address="456 Oak Ave, Vacaville, CA",
        location_type="dmv",
        notes="Tuesdays are renewal day - best revenue. Long wait times = hungry customers."
    )
    print(f"   ✅ Created location: {dmv['name']}")

    sheriff = await location_service.create(
        org_id=org_id,
        name="Sheriff's Office",
        latitude=38.2494,
        longitude=-122.0400,
        address="600 Union Ave, Fairfield, CA",
        location_type="government",
        notes="Hidden goldmine on Fridays. Consistent lunch crowd."
    )
    print(f"   ✅ Created location: {sheriff['name']}")

    downtown = await location_service.create(
        org_id=org_id,
        name="Downtown Vacaville",
        latitude=38.3566,
        longitude=-121.9900,
        address="Downtown Vacaville, CA",
        location_type="downtown",
        notes="Farmers market nearby on weekends. Morning shoppers + lunch crowd."
    )
    print(f"   ✅ Created location: {downtown['name']}")

    # ===========================================
    # 4. Create Carts
    # ===========================================
    print("\n🛒 Creating carts...")

    cart1 = await cart_service.create(
        org_id=org_id,
        name="Cart 1 - Main (Poncho)",
        hardware_id=None  # Will be set when Pi is registered
    )
    await cart_service.update_status(cart1["id"], "active")
    print(f"   ✅ Created cart: {cart1['name']}")

    cart2 = await cart_service.create(
        org_id=org_id,
        name="Cart 2 - Brother-in-law",
        hardware_id=None
    )
    await cart_service.update_status(cart2["id"], "active")
    print(f"   ✅ Created cart: {cart2['name']}")

    cart3 = await cart_service.create(
        org_id=org_id,
        name="Cart 3 - New Hire",
        hardware_id=None
    )
    await cart_service.update_status(cart3["id"], "active")
    print(f"   ✅ Created cart: {cart3['name']}")

    # ===========================================
    # 5. Create Sample Transactions
    # ===========================================
    print("\n💰 Creating sample transactions...")

    # Generate transactions for the past 2 weeks
    # This demonstrates the location patterns Poncho discovered
    today = datetime.now()
    transaction_count = 0

    for days_ago in range(14):
        date = today - timedelta(days=days_ago)
        day_of_week = date.weekday()  # 0=Monday, 6=Sunday

        # Skip weekends for now
        if day_of_week >= 5:
            continue

        # Courthouse patterns
        # Thursday (3) = jury duty = $890 avg
        # Wednesday (2) = regular = $510 avg
        if day_of_week == 3:  # Thursday
            base_revenue = 890
            location_id = courthouse["id"]
        elif day_of_week == 2:  # Wednesday
            base_revenue = 510
            location_id = courthouse["id"]
        # DMV patterns
        # Tuesday (1) = renewal day = $850 avg
        # Other days = $420-580 avg
        elif day_of_week == 1:  # Tuesday
            base_revenue = 850
            location_id = dmv["id"]
        elif day_of_week == 0:  # Monday
            base_revenue = 420
            location_id = dmv["id"]
        # Friday = Sheriff's Office
        elif day_of_week == 4:  # Friday
            base_revenue = 820
            location_id = sheriff["id"]
        else:
            continue

        # Create multiple transactions to sum to the daily revenue
        # Average transaction is about $13
        num_transactions = base_revenue // 13
        for i in range(num_transactions):
            import random
            amount = random.uniform(8.0, 32.0)  # $8 to $32 per transaction

            items = []
            if amount < 12:
                items = [{"name": "Classic Dog", "quantity": 1, "price": amount}]
            elif amount < 20:
                items = [{"name": "Dirty Water Dog", "quantity": 1, "price": 10.0},
                         {"name": "Drink", "quantity": 1, "price": amount - 10}]
            else:
                items = [{"name": "Dirty Water Dog", "quantity": 2, "price": 20.0},
                         {"name": "Brisket Dog", "quantity": 1, "price": amount - 20}]

            hour = random.randint(10, 17)
            minute = random.randint(0, 59)
            timestamp = date.replace(hour=hour, minute=minute).isoformat() + "Z"

            await transaction_service.create(
                org_id=org_id,
                cart_id=cart1["id"],
                location_id=location_id,
                amount=round(amount, 2),
                timestamp=timestamp,
                items=items,
                payment_method=random.choice(["card", "card", "card", "cash"])  # 75% card
            )
            transaction_count += 1

    print(f"   ✅ Created {transaction_count} sample transactions")

    # ===========================================
    # 6. Create Sample Quality Checks
    # ===========================================
    print("\n📸 Creating sample quality checks...")

    check_types = ["dirty_water", "garlic_butter", "cart_display"]
    quality_count = 0

    for days_ago in range(7):
        date = today - timedelta(days=days_ago)
        if date.weekday() >= 5:
            continue

        # Poncho always completes checks
        for check_type in check_types:
            timestamp = date.replace(hour=10, minute=15).isoformat() + "Z"
            await quality_check_service.create(
                org_id=org_id,
                cart_id=cart1["id"],
                employee_id=poncho["id"],
                check_type=check_type,
                photo_url=f"https://storage.supabase.co/quality/{check_type}_{date.strftime('%Y%m%d')}.jpg"
            )
            quality_count += 1

        # Brother-in-law sometimes misses checks (71.4% completion rate)
        import random
        for check_type in check_types:
            if random.random() < 0.714:  # 71.4% chance of completing
                timestamp = date.replace(hour=10, minute=45).isoformat() + "Z"
                await quality_check_service.create(
                    org_id=org_id,
                    cart_id=cart2["id"],
                    employee_id=brother["id"],
                    check_type=check_type,
                    photo_url=f"https://storage.supabase.co/quality/{check_type}_{date.strftime('%Y%m%d')}_c2.jpg"
                )
                quality_count += 1

    print(f"   ✅ Created {quality_count} sample quality checks")

    # ===========================================
    # Summary
    # ===========================================
    print("\n" + "=" * 50)
    print("🎉 EatFireCraft seed data complete!")
    print("=" * 50)
    print(f"""
Organization: {org['name']}
Org ID: {org_id}

Users:
  - Poncho (owner): {poncho['id']}
  - Brother-in-law (operator): {brother['id']}
  - New Hire (employee): {new_hire['id']}

Locations:
  - Courthouse: {courthouse['id']}
  - DMV: {dmv['id']}
  - Sheriff's Office: {sheriff['id']}
  - Downtown: {downtown['id']}

Carts:
  - Cart 1: {cart1['id']}
  - Cart 2: {cart2['id']}
  - Cart 3: {cart3['id']}

Transactions: {transaction_count}
Quality Checks: {quality_count}

Key patterns seeded:
  - Thursday courthouse: ~$890/day (jury duty)
  - Wednesday courthouse: ~$510/day (regular)
  - Tuesday DMV: ~$850/day (renewal day)
  - Friday Sheriff: ~$820/day (hidden goldmine)
""")

    return org_id


if __name__ == "__main__":
    asyncio.run(seed_eatfirecraft())
