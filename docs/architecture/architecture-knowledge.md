# FoodCartOS — Architecture & Project Knowledge

> **Purpose:** This document provides comprehensive project context for AI assistants (Claude Desktop, etc.). It covers architecture, data flows, implementation status, and domain context so any conversation can reason about the codebase without exploring files.
>
> **Last updated:** 2026-02-23

---

## 1. What Is FoodCartOS?

An open-source operating system for food cart entrepreneurs, helping them scale from 1–3 carts to multi-location operations while maintaining brand quality.

**First customer:** EatFireCraft — Poncho's hot dog cart business in Vacaville, CA.

### The Core Problem

Poncho was losing **$19,760/year** by going to the courthouse on Wednesdays ($510/day) instead of Thursdays ($890/day — jury duty days). He had no data to know this.

**Three pain points:**
1. **Location blindness** — No data on which location/day combinations are profitable
2. **Employee trust** — Can't verify quality standards without being present
3. **Brand fear** — "I don't want the brand to water down"

### Design Principles

1. **Offline-first** — Carts have poor connectivity; must work without internet
2. **Simple UX** — "Big buttons, pictures, done" — food cart owners aren't tech people
3. **Quick value** — Show ROI in 2 weeks, not 6 months
4. **Brand protection** — Every feature should help maintain quality standards

---

## 2. Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI |
| Database | Supabase (PostgreSQL), dedicated `foodcartos` schema |
| Frontend | Jinja2 templates + HTMX + PicoCSS (server-rendered, zero JS frameworks) |
| Auth | Dual — session cookies for browser pages, JWT for API routes |
| Payments | Square POS integration |
| Messaging | Twilio SMS |
| Delivery | DoorDash, UberEats, Grubhub, SMS pre-orders |
| Social | Instagram, Facebook, TikTok, Google Business Profile |
| Hardware (planned) | Raspberry Pi 4 + SIM7600A-H (cellular + GPS + camera) |
| Automation (planned) | n8n workflows |
| PWA | Service worker + manifest for offline shell caching |

---

## 3. Directory Structure

```
foodcartos/
├── app/
│   ├── main.py              # FastAPI entry point, middleware, router registration
│   ├── config.py            # Pydantic Settings from .env
│   ├── routers/
│   │   ├── pages.py         # All HTML page routes (718 lines, largest file)
│   │   ├── auth.py          # API JWT auth (stub — 501 responses)
│   │   ├── locations.py     # Location intelligence API
│   │   ├── transactions.py  # Revenue data API
│   │   ├── carts.py         # Cart management API (mostly stub)
│   │   ├── orders.py        # Unified order management API
│   │   ├── quality.py       # Photo verification API (mostly stub)
│   │   ├── social.py        # Social media management API + OAuth callbacks
│   │   └── webhooks.py      # Incoming webhooks (Square, Twilio, DoorDash, etc.)
│   ├── services/
│   │   ├── supabase.py      # Core DB layer — 7 service classes
│   │   ├── auth.py          # Session auth (bcrypt, register/login)
│   │   ├── square.py        # Square POS integration
│   │   ├── delivery_platforms/
│   │   │   ├── base.py      # Abstract base + NormalizedOrder model
│   │   │   ├── doordash.py  # DoorDash Marketplace + Drive API
│   │   │   ├── ubereats.py  # UberEats OAuth2
│   │   │   ├── grubhub.py   # Grubhub webhooks
│   │   │   └── sms_preorder.py  # Twilio SMS ordering flow
│   │   └── social_media/
│   │       ├── base.py      # Abstract base + SocialPost model
│   │       ├── content_generator.py  # Template-based post generation
│   │       ├── publisher.py # Post lifecycle (draft → approve → publish)
│   │       ├── instagram.py, facebook.py, tiktok.py, google_business.py
│   ├── templates/           # Jinja2 templates (see Section 6)
│   └── static/              # CSS, PWA manifest, service worker, icons
├── docs/                    # Project documentation
├── scripts/
│   └── seed_eatfirecraft.py # Demo data seeder (534 transactions, 29 quality checks)
├── supabase/
│   └── migrations/          # 7 SQL migration files (see Section 5)
├── make_gif.py              # PIL-based GIF stitcher for demo walkthroughs
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Dev/test dependencies
└── CLAUDE.md                # Claude Code project instructions
```

---

## 4. Application Architecture

### 4.1 Entry Point (`app/main.py`)

FastAPI app with:
- **Middleware stack** (order matters): `SessionMiddleware` first (secret key, 7-day max age), then `CORSMiddleware`
- **Static files** mounted at `/static`
- **9 routers** registered with prefix/tag configuration
- **Health check** at `GET /health`

### 4.2 Authentication — Dual System

**Session auth (browser pages):**
- Used by `pages.py` for all HTML routes
- `SessionMiddleware` stores user_id, org_id, user_name, user_role in cookie
- Password hashed with `bcrypt.hashpw()` directly (not passlib — incompatible with bcrypt >=4.1)
- Password hash stored in `users.settings` JSONB field (not a dedicated column)
- `onboarding_complete` and `onboarding_step` also in `users.settings`

**JWT auth (API routes):**
- Defined in `auth.py` router but **currently stub (501 responses)**
- Session auth in `pages.py` is the only live auth path today

**Important:** Page routes use admin Supabase services (`use_admin=True`) to bypass RLS, since session cookies don't carry JWT claims that RLS policies expect.

### 4.3 Supabase Service Layer (`app/services/supabase.py`)

All services operate in the `foodcartos` schema. Two client modes:

```
┌─────────────────────────┐     ┌─────────────────────────┐
│   Anon Client           │     │   Admin Client           │
│   (respects RLS)        │     │   (bypasses RLS)         │
│   For API routes w/JWT  │     │   For page routes,       │
│                         │     │   admin ops, seeding     │
└─────────────────────────┘     └─────────────────────────┘
```

**SupabaseService** base class provides `self.table(name)` which calls `client.schema("foodcartos").table(name)`.

**7 service classes:**

| Service | Key Methods |
|---------|-------------|
| `OrganizationService` | create, get_by_slug, get_by_id, list_all |
| `UserService` | create, get_by_email, list_by_org |
| `LocationService` | create, list_by_org (with type filter), get_by_id |
| `CartService` | create, list_by_org, update_status |
| `TransactionService` | create (computes day_of_week), list_by_date_range, get_daily_summary |
| `QualityCheckService` | create, list_by_cart_date, update_status |
| `OrderService` | create, get_by_id, get_by_external_id, update_status, list_active, get_daily_order_stats |

Module-level singletons (anon mode) are exported for import convenience. Admin mode requires explicit instantiation: `OrganizationService(use_admin=True)`.

### 4.4 Router Detail

#### `pages.py` (718 lines) — The Heart of the App

All browser-facing HTML routes. The largest and most important file.

**Route groups:**
- `/login`, `/logout`, `/register` — Session auth flow
- `/onboarding/step/1` through `/step/7` — 7-step onboarding wizard
- `/dashboard` — Main dashboard (today's revenue, carts, locations)
- `/dashboard/heatmap` — Dark-themed heatmap & analytics
- `/dashboard/social` — Dark-themed social & data sources
- `/dashboard/locations` — 30-day location performance
- `/dashboard/quality` — Today's quality checks with HTMX approve/reject
- `/settings/account`, `/settings/social` — Settings pages

**Helper functions:** `_session()`, `_redirect()` (handles HX-Redirect for HTMX), `_flash()`, `_pop_flash()`, `_ctx()`, `_require_auth()`

#### `locations.py` (369 lines) — Location Intelligence

The flagship feature. Real Supabase integration.

- `GET /api/locations/recommendations` — Ranks locations by predicted revenue for a target date using historical day-of-week patterns. Returns HIGH/MEDIUM/LOW confidence tiers.
- `GET /api/locations/{id}/performance` — 30-day day-of-week analysis (the "jury duty Thursday" insight)
- `GET /api/locations/{id}/compare` — Compares two locations, returns Switch/Stay/Similar recommendation

#### `webhooks.py` (509 lines) — External Integrations

Incoming webhooks from: Square, Twilio SMS, n8n, DoorDash, UberEats, Grubhub, Meta, Hardware Agent. Signature verification gated on `APP_ENV == "production"`.

#### `social.py` (584 lines) — Social Media Automation

Account management, post lifecycle, SMS-based approval flow, OAuth callbacks for 4 platforms. OAuth state format: `"org_id|context"` where context is `"onboarding"` or `"settings"`.

#### `orders.py` (303 lines) — Unified Orders

All delivery platforms normalize to a unified order format. Endpoints for the "ticket rail" (active orders), daily stats by platform, and status management.

---

## 5. Database Schema

All tables live in the `foodcartos` schema (isolated from other apps on the same Supabase instance).

### 5.1 Entity-Relationship Overview

```
organizations (tenant)
  ├── users (owner/operator/employee)
  ├── locations (GPS coordinates, type, active flag)
  ├── carts (hardware_id, current_location, status)
  ├── daily_assignments (cart ↔ location ↔ employee for a date)
  ├── transactions (from Square — amount, items, day_of_week, weather)
  ├── quality_checks (photo_url, check_type, status, reviewer)
  ├── gps_pings (latitude, longitude, accuracy, timestamp)
  ├── sms_subscribers (phone, favorite_locations, last_order)
  ├── sms_messages (direction, twilio_sid, body, status)
  ├── orders (unified across all platforms — see delivery platforms)
  ├── social_accounts (platform tokens, settings)
  ├── social_posts (caption, media, status lifecycle, approval tracking)
  └── social_templates (trigger-based caption templates)
```

### 5.2 Key Design Decisions

- **Multi-tenant via org_id:** Every table has `org_id` FK to `organizations`
- **RLS (Row Level Security):** All tables have RLS enabled. Policies use JWT claims (`auth.jwt()->>'org_id'`, `->>'role'`, `->>'sub'`) via SECURITY DEFINER helper functions
- **`service_role` bypasses RLS:** No need for INSERT policies targeting service_role — they're redundant and accidentally permissive (fixed in migration 007)
- **User settings as JSONB:** `password_hash`, `onboarding_complete`, `onboarding_step` stored in `users.settings` column
- **Day-of-week on transactions:** Computed at insert time (Sunday=0) for efficient location pattern queries
- **Unified orders:** `order_platform` enum + `external_id` for cross-platform deduplication

### 5.3 Migrations (7 files in `supabase/migrations/`)

| Migration | Purpose |
|-----------|---------|
| `000_create_schema.sql` | Creates `foodcartos` schema, grants to roles |
| `001_initial_schema.sql` | Core 10 tables + `update_updated_at()` trigger |
| `002_row_level_security.sql` | RLS policies + helper functions (get_user_org_id, etc.) |
| `003_grant_service_role.sql` | Explicit GRANT ALL to service_role |
| `004_orders_table.sql` | Unified orders table with platform/status enums |
| `005_social_media.sql` | social_accounts, social_posts, social_templates |
| `006_user_auth_columns.sql` | No-op documenting that auth fields live in settings JSONB |
| `007_fix_security_warnings.sql` | Fixes search_path on functions + drops overly-permissive INSERT policies |

**Not yet applied:** `orders` and `social_accounts` tables may not be in production Supabase. Code guards with try/except.

---

## 6. Frontend Architecture

### Template Hierarchy

```
base.html (PicoCSS + HTMX + custom CSS + PWA)
  ├── auth/login.html
  ├── onboarding/welcome.html (step 1)
  ├── onboarding/square_connect.html (step 2)
  ├── onboarding/locations.html (step 3)
  ├── onboarding/carts.html (step 4)
  ├── onboarding/quality_setup.html (step 5)
  ├── onboarding/social_connect.html (step 6)
  ├── onboarding/dashboard_preview.html (step 7)
  ├── dashboard/index.html
  ├── dashboard/locations.html
  ├── dashboard/quality.html (HTMX approve/reject)
  ├── settings/account.html
  └── settings/social.html

STANDALONE (do NOT extend base.html — self-contained dark-theme CSS):
  ├── dashboard/heatmap.html (552 lines — traffic heatmap, map, leaderboard, deploy planner)
  └── dashboard/social.html (364 lines — connections, auto-posts, calendar, reviews)
```

**Components** (included via `{% include %}`): nav.html, footer.html, card.html, step_indicator.html

**Key frontend patterns:**
- Server-rendered with Jinja2 — no client-side JS framework
- HTMX for dynamic interactions (form submissions, partial page updates)
- PicoCSS as the base CSS framework
- Brand color: orange `#e25822`
- Flash messages via session

---

## 7. Data Flow Diagrams

### 7.1 Square Payment → Dashboard

```
Square POS → POST /webhooks/square
  → verify_webhook_signature() (production only)
  → process_payment_webhook()
    → TransactionService.create() (computes day_of_week)
      → foodcartos.transactions table
        → Location performance queries (day-of-week patterns)
          → GET /api/locations/recommendations
```

### 7.2 Quality Check → Social Post

```
Employee takes photo → POST /api/quality/checks
  → QualityCheckService.create()
Owner approves → PATCH /api/quality/checks/{id} (status=approved)
  → ContentGeneratorService.generate_from_quality_check()
    → PostPublisherService.handle_new_post()
      → If auto_approve: publish immediately to connected platforms
      → Else: send SMS approval link via Twilio
        → Owner clicks approve link → GET /api/social/approve/{id}
          → publish_post() → Instagram/Facebook/TikTok/Google
```

### 7.3 Delivery Order Flow

```
DoorDash/UberEats/Grubhub webhook → POST /webhooks/{platform}
  → Platform service.parse_order() → NormalizedOrder
    → OrderService.create() → foodcartos.orders table
      → GET /api/orders/active (the "ticket rail")

SMS: Customer texts "ORDER" → POST /webhooks/twilio/sms
  → sms_preorder_service routes the message
    → Sends menu → Customer replies with order → Parse → Create order
```

### 7.4 Location Recommendation Engine

```
GET /api/locations/recommendations?target_date=2026-02-27

1. Fetch all org locations
2. For each location, query transactions for last 30 days
3. Group by day_of_week, compute average revenue per weekday
4. For target_date's weekday, get the average for each location
5. Assign confidence: HIGH (≥4 data points), MEDIUM (2-3), LOW (0-1)
6. Sort by predicted revenue descending
7. Return ranked recommendations
```

---

## 8. External Service Integrations

### Square POS
- SDK v33+ (`from square import Square`)
- Webhook types: payment.completed, payment.updated, refund.created
- Historical sync via `sync_transactions_from_square()`

### Twilio SMS
- Inbound SMS routing (orders, conversations)
- Outbound: order confirmations, social post approval links, daily revenue summaries
- Webhook signature verification

### Delivery Platforms
All normalize to `NormalizedOrder` dataclass with unified fields.

| Platform | Auth | Capabilities |
|----------|------|-------------|
| DoorDash | ECDSA JWT | Marketplace + Drive API (use DoorDash drivers) |
| UberEats | OAuth2 | Order webhooks, status updates, token refresh |
| Grubhub | API key | Order webhooks, status updates |
| SMS | Twilio | Natural language order parsing |

### Social Media
All implement `SocialMediaService` ABC.

| Platform | Auth | Features |
|----------|------|----------|
| Instagram | OAuth2 | Photo/video publish, analytics |
| Facebook | OAuth2 | Page posts, analytics |
| TikTok | OAuth2 | Video publish, analytics |
| Google Business | OAuth2 | Posts, analytics |

---

## 9. Implementation Status

### Complete
- FastAPI routing + middleware stack
- Session auth (register/login/logout with bcrypt)
- 7-step onboarding wizard (business → Square → locations → carts → quality → social → preview)
- All dashboard pages (main, heatmap, social, locations, quality)
- Settings pages (account, social)
- Supabase service layer (7 entity services, admin mode)
- Square webhook processing + historical sync
- Location performance analysis + day-of-week recommendations
- Transaction CRUD + summaries + trends + comparison
- Social media OAuth flows (4 platforms) + post lifecycle
- Delivery platform webhooks (DoorDash, UberEats, Grubhub)
- SMS pre-order flow
- Database schema + RLS policies (7 migrations)
- Seed data (EatFireCraft: 534 transactions, 29 quality checks, 4 locations, 3 carts)
- PWA manifest + service worker
- Dark-themed standalone dashboards (heatmap, social)

### Stub / Partial
- API JWT auth router (501 responses — session auth is the live path)
- Cart management API (model definitions complete, endpoints return stub data)
- Quality checks API (model definitions complete, endpoints return stub data)

### Not Started
- n8n workflow JSON files
- Hardware agent code (Raspberry Pi + SIM7600A-H)
- Platform-to-store mapping (DoorDash store IDs → our locations)
- Test suite (infrastructure declared in requirements-dev.txt, no test files)
- Apply `orders` and `social_accounts` migrations to production Supabase

---

## 10. Configuration

All settings in `app/config.py` via Pydantic `BaseSettings`, read from `.env`.

**Setting groups:** App (env, debug, secrets), Session, URLs, Supabase (URL + keys + schema), Square, Twilio, Weather (OpenWeather), n8n, DoorDash, UberEats, Grubhub, Hardware Agent, Social (Meta, TikTok, Google).

**Key defaults:**
- `DATABASE_SCHEMA = "foodcartos"`
- `SESSION_MAX_AGE = 604800` (7 days)
- `GPS_UPDATE_INTERVAL = 300` (5 min)
- `SYNC_INTERVAL = 60` (1 min)
- `OFFLINE_QUEUE_MAX_SIZE = 1000`

---

## 11. Known Gotchas

1. **RLS + GRANTs:** Supabase requires BOTH an RLS policy AND a GRANT for a role to access a table. Missing either → 401/403.
2. **`service_role` bypasses RLS:** Don't create INSERT policies "for service role" with `WITH CHECK (TRUE)` — they accidentally open tables to anon/authenticated.
3. **Square SDK v33+:** Use `from square import Square` and `Square(token=...)` — old `Client` import is gone.
4. **bcrypt:** Use `bcrypt.hashpw()`/`bcrypt.checkpw()` directly — passlib 1.7.4 is incompatible with bcrypt >=4.1.
5. **Page routes need admin services:** `use_admin=True` bypasses RLS since session cookies don't carry JWT claims.
6. **User auth in JSONB:** `password_hash`, `onboarding_complete`, `onboarding_step` stored in `users.settings` column (not dedicated columns).
7. **Missing tables:** `social_accounts` and `orders` tables require migrations not yet applied — guard queries with try/except.
8. **Dark-theme dashboards are standalone:** `heatmap.html` and `social.html` do NOT extend `base.html` — they carry their own CSS to avoid PicoCSS conflicts.
9. **Shared Supabase instance:** The `foodcartos` schema shares the Supabase project with `jeweledtech`. Only `foodcartos.*` security warnings are relevant.

---

## 12. Domain Context

### Key Personas

**Poncho (Owner):**
- Runs EatFireCraft hot dog carts in Vacaville, CA
- Vision: "I'm going to be the new In-N-Out"
- Biggest fear: brand quality dilution as he scales
- Growth blocker: location intelligence ("Location is what stops me from cart #4")
- Not tech-savvy — needs "big buttons, pictures, done"

### Key Metrics
- Thursday courthouse: ~$890/day (jury duty crowds)
- Wednesday courthouse: ~$510/day (normal day)
- Tuesday DMV: ~$850/day (renewal day)
- Annual loss from wrong-day scheduling: ~$19,760

### Product Decisions Filter
> "Would Poncho understand this? Does it protect his brand quality?"

---

## 13. Commands Reference

```bash
# Run backend
source venv/bin/activate && python -m uvicorn app.main:app --reload

# Seed demo data
source venv/bin/activate && python scripts/seed_eatfirecraft.py

# Run tests
pytest

# Format code
black . && ruff check .

# Push migrations to Supabase
npx supabase db push --linked
```

---

## 14. Key File Quick Reference

| Need to understand... | Read this file |
|----------------------|----------------|
| All page routes & onboarding | `app/routers/pages.py` |
| Database access patterns | `app/services/supabase.py` |
| Auth flow | `app/services/auth.py` |
| Location intelligence | `app/routers/locations.py` |
| Webhook handling | `app/routers/webhooks.py` |
| Social media automation | `app/routers/social.py` + `app/services/social_media/` |
| Delivery platform integration | `app/services/delivery_platforms/` |
| Database schema | `supabase/migrations/` (read in order) |
| Customer psychology | `docs/personas/README.md` |
| Business model | `docs/business-models/README.md` |
| Hardware architecture | `docs/hardware/README.md` |
| Template structure | `app/templates/base.html` + subdirectories |
| Dev setup | `docs/setup/README.md` |
