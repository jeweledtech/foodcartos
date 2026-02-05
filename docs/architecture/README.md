# FoodCartOS Architecture Overview

This document explains how FoodCartOS works, from hardware in the cart to dashboards on your phone. Understanding this architecture helps you:
- Set up new installations
- Debug issues
- Extend functionality
- Explain the system to clients

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FOOD CART (Hardware)                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Square POS   │  │ Raspberry Pi │  │   Camera     │              │
│  │   Reader     │  │   4 (arm64)  │  │   Module     │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│         │    ┌────────────┴────────────┐    │                       │
│         │    │                         │    │                       │
│         ▼    ▼                         ▼    ▼                       │
│  ┌─────────────────┐           ┌─────────────────┐                 │
│  │   SIM7600A-H    │           │    ESP32-S3     │                 │
│  │ (LTE + GPS)     │           │  (WiFi Scanner) │                 │
│  └────────┬────────┘           └────────┬────────┘                 │
│           │                             │                           │
│           └──────────────┬──────────────┘                           │
│                          │                                          │
│                    ┌─────▼─────┐                                    │
│                    │  SQLite   │  ← Offline-capable local storage   │
│                    │  (Local)  │                                    │
│                    └─────┬─────┘                                    │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
                           │ Cellular (LTE) / WiFi
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                            CLOUD                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   Supabase   │◄───│    n8n       │───►│   Twilio     │          │
│  │ (PostgreSQL) │    │ (Workflows)  │    │   (SMS)      │          │
│  └──────┬───────┘    └──────┬───────┘    └──────────────┘          │
│         │                   │                                        │
│         │    ┌──────────────┴──────────────┐                        │
│         │    │                             │                        │
│         ▼    ▼                             ▼                        │
│  ┌─────────────────┐           ┌─────────────────┐                 │
│  │   FastAPI       │           │  Social APIs    │                 │
│  │   Backend       │           │ (IG, FB, etc)   │                 │
│  └────────┬────────┘           └─────────────────┘                 │
│           │                                                          │
└───────────┼──────────────────────────────────────────────────────────┘
            │
            │ HTTPS
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                     │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Owner      │  │  Operator    │  │  Employee    │              │
│  │  Dashboard   │  │    App       │  │    App       │              │
│  │   (Web)      │  │   (PWA)      │  │   (PWA)      │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Layer-by-Layer Breakdown

### Layer 1: Cart Hardware

The physical devices installed in each food cart.

#### Raspberry Pi 4 (Brain)
- **Specs:** 4GB+ RAM, arm64 architecture
- **OS:** Raspberry Pi OS Lite (64-bit)
- **Role:** Coordinates all hardware, runs local database, syncs to cloud
- **Mounting:** Weatherproof enclosure, powered by cart's electrical system

```python
# Hardware abstraction in code
class CartController:
    def __init__(self):
        self.gps = SIM7600GPS()
        self.cellular = SIM7600LTE()
        self.camera = PiCamera()
        self.wifi_scanner = ESP32Scanner()
        self.local_db = SQLiteDB("cart.db")
```

#### SIM7600A-H HAT (Connectivity + Location)
- **LTE:** 4G cellular data via T-Mobile IoT SIM (~$10/month for 5GB)
- **GPS:** Built-in GPS module for location tracking
- **Antennas:** Dual antennas (LTE + GPS) mounted on cart exterior

#### ESP32-S3 XIAO (Foot Traffic)
- **Function:** Scans WiFi networks and Bluetooth beacons to estimate crowd size
- **Privacy:** MACs are hashed locally, never stored raw
- **Communication:** Serial to Raspberry Pi

#### Camera Module
- **Function:** Photo verification (quality checks, setup proof)
- **Resolution:** 5MP minimum for readable photos
- **Storage:** Local first, then uploaded to cloud

#### Square Card Reader
- **Function:** Payment processing
- **Integration:** Square API webhooks for real-time transaction data
- **Cost:** Free hardware with Square account

---

### Layer 2: Local Data (SQLite)

Each cart maintains its own SQLite database for offline operation.

```sql
-- Core tables (simplified)
CREATE TABLE transactions (
    id TEXT PRIMARY KEY,
    square_id TEXT,
    amount DECIMAL(10,2),
    items JSON,
    timestamp DATETIME,
    synced BOOLEAN DEFAULT FALSE
);

CREATE TABLE quality_checks (
    id TEXT PRIMARY KEY,
    check_type TEXT,  -- 'dirty_water', 'garlic_butter', 'cart_display'
    photo_path TEXT,
    employee_id TEXT,
    timestamp DATETIME,
    synced BOOLEAN DEFAULT FALSE
);

CREATE TABLE location_pings (
    id TEXT PRIMARY KEY,
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    timestamp DATETIME,
    synced BOOLEAN DEFAULT FALSE
);
```

**Why SQLite?**
- Works without internet
- Survives cellular dead zones
- Syncs when connection returns
- Poncho's carts are sometimes in parking lots with poor signal

---

### Layer 3: Cloud Database (Supabase)

Central PostgreSQL database with Row-Level Security for multi-tenant isolation.

#### Key Tables

```sql
-- Organizations (tenants)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,  -- 'eatfirecraft'
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users with roles
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    email TEXT UNIQUE NOT NULL,
    role TEXT CHECK (role IN ('owner', 'operator', 'employee')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Carts
CREATE TABLE carts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    name TEXT NOT NULL,
    hardware_id TEXT UNIQUE,  -- Raspberry Pi serial
    current_location_id UUID REFERENCES locations(id),
    status TEXT DEFAULT 'inactive'
);

-- Locations
CREATE TABLE locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    name TEXT NOT NULL,
    address TEXT,
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    location_type TEXT,  -- 'dmv', 'courthouse', 'event', etc.
    notes TEXT
);

-- Transactions (from Square)
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    cart_id UUID REFERENCES carts(id),
    location_id UUID REFERENCES locations(id),
    square_id TEXT UNIQUE,
    amount DECIMAL(10,2) NOT NULL,
    items JSONB,
    timestamp TIMESTAMPTZ NOT NULL,
    day_of_week INTEGER,  -- 0=Sunday, 6=Saturday
    weather JSONB  -- Captured at time of transaction
);

-- Quality Checks
CREATE TABLE quality_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    cart_id UUID REFERENCES carts(id),
    employee_id UUID REFERENCES users(id),
    check_type TEXT NOT NULL,
    photo_url TEXT,
    status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    notes TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Daily Assignments
CREATE TABLE daily_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    cart_id UUID REFERENCES carts(id),
    location_id UUID REFERENCES locations(id),
    employee_id UUID REFERENCES users(id),
    date DATE NOT NULL,
    shift_start TIME,
    shift_end TIME,
    status TEXT DEFAULT 'scheduled'
);
```

#### Row-Level Security (Multi-Tenant)

```sql
-- Users can only see their organization's data
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own org transactions"
ON transactions FOR SELECT
USING (org_id = auth.jwt()->>'org_id');

-- Employees see limited data
CREATE POLICY "Employees see own quality checks"
ON quality_checks FOR SELECT
USING (
    org_id = auth.jwt()->>'org_id'
    AND (
        auth.jwt()->>'role' IN ('owner', 'operator')
        OR employee_id = auth.jwt()->>'user_id'
    )
);
```

---

### Layer 4: Backend API (FastAPI)

RESTful API that connects frontend to database and handles business logic.

#### Project Structure

```
app/
├── main.py              # FastAPI application entry
├── config.py            # Environment configuration
├── models/
│   ├── user.py
│   ├── cart.py
│   ├── location.py
│   ├── transaction.py
│   └── quality_check.py
├── routers/
│   ├── auth.py          # Authentication endpoints
│   ├── carts.py         # Cart management
│   ├── locations.py     # Location CRUD + intelligence
│   ├── transactions.py  # Revenue data
│   ├── quality.py       # Photo verification
│   └── webhooks.py      # Square, Twilio callbacks
├── services/
│   ├── square.py        # Square API integration
│   ├── twilio.py        # SMS messaging
│   ├── location_intel.py # Location scoring algorithm
│   └── weather.py       # Weather API integration
└── utils/
    ├── auth.py          # JWT handling
    └── storage.py       # File uploads (photos)
```

#### Key Endpoints

```python
# Location Intelligence
@router.get("/locations/{location_id}/performance")
async def get_location_performance(location_id: str):
    """
    Returns performance metrics for a location:
    - Average daily revenue
    - Day-of-week patterns
    - Weather impact
    - Comparison to other locations
    """

@router.get("/locations/recommendations")
async def get_location_recommendations(cart_id: str, date: str):
    """
    Returns ranked location recommendations for a specific cart/date:
    - Predicted revenue
    - Confidence score
    - Reasoning (jury duty day, good weather, etc.)
    """

# Quality Verification
@router.post("/quality-checks")
async def submit_quality_check(
    check_type: str,
    photo: UploadFile,
    cart_id: str,
    employee_id: str
):
    """
    Handles morning checklist submissions:
    - Stores photo in cloud storage
    - Creates quality_check record
    - Triggers n8n workflow for notification
    """

# Webhooks
@router.post("/webhooks/square")
async def square_webhook(payload: dict):
    """
    Receives real-time transaction data from Square:
    - Validates webhook signature
    - Creates transaction record
    - Triggers revenue update workflows
    """
```

---

### Layer 5: Automation (n8n)

n8n workflows handle all automated processes.

#### Core Workflows

**1. Morning Checklist Verification**
```
Trigger: Quality check submitted
→ Check if all required photos uploaded
→ If complete: Update employee status to "checked in"
→ If incomplete after 30 min: Alert owner via SMS
→ Store completion time for performance tracking
```

**2. Daily Revenue Summary**
```
Trigger: 9 PM daily (cron)
→ Pull all transactions for today
→ Group by cart and location
→ Compare to historical averages
→ Generate summary message
→ Send SMS to owner
→ Post to Slack (if configured)
```

**3. Location Recommendation**
```
Trigger: 6 AM daily (cron)
→ Get tomorrow's weather forecast
→ Check for local events
→ Calculate predicted revenue per location
→ Generate recommendations
→ Send to owner for approval
```

**4. Customer SMS Marketing**
```
Trigger: Cart arrives at location (GPS fence)
→ Look up customers who opted in for this location
→ Send "We're at [location] until [time]" message
→ Include today's special (if any)
→ Track message delivery and clicks
```

---

### Layer 6: Frontend (PWA)

Mobile-first Progressive Web App that works on phones, tablets, and desktops.

#### Three User Interfaces

**Owner Dashboard (Poncho's view)**
- All carts at a glance
- Revenue trends and comparisons
- Location performance heat map
- Employee quality scores
- Financial reports

**Operator App (Cart manager's view)**
- Assigned cart for today
- Check-in/check-out
- View own performance
- Submit quality photos
- See basic revenue (own cart only)

**Employee App (Simplest view)**
- Today's assignment
- Checklist with photo upload
- Own quality score
- Clock in/out

#### Tech Stack

```
Frontend/
├── src/
│   ├── components/
│   │   ├── Dashboard/
│   │   ├── LocationMap/
│   │   ├── QualityChecklist/
│   │   ├── RevenueChart/
│   │   └── common/
│   ├── pages/
│   │   ├── owner/
│   │   ├── operator/
│   │   └── employee/
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useRealtime.ts  # Supabase subscriptions
│   │   └── useOffline.ts   # PWA offline support
│   └── services/
│       └── api.ts
├── public/
│   └── manifest.json       # PWA manifest
└── package.json
```

#### Design Principles

> "Big buttons, pictures, done." — Design requirement from Poncho interview

1. **Touch-first:** All buttons minimum 44x44px
2. **Minimal text:** Icons and visuals over words
3. **Instant feedback:** Loading states, success confirmations
4. **Offline-capable:** Core features work without internet
5. **Fast:** <3 second initial load, <1 second interactions

---

## Data Flow Examples

### Example 1: Transaction Recording

```
1. Customer pays at Square reader
2. Square sends webhook to /webhooks/square
3. FastAPI validates and stores transaction
4. Supabase triggers realtime event
5. Owner dashboard updates instantly
6. n8n checks if daily threshold reached
7. If milestone: Send celebration SMS to owner
```

### Example 2: Morning Check-In

```
1. Employee opens app at 10:30 AM
2. App shows checklist: dirty water, garlic butter, cart display
3. Employee takes photo of dirty water setup
4. Photo uploads to Supabase Storage
5. quality_check record created
6. n8n workflow triggered
7. If all 3 photos submitted: Mark shift as started
8. If photos missing after 11 AM: Alert owner
```

### Example 3: Location Recommendation

```
1. n8n cron fires at 6 AM
2. Workflow fetches tomorrow's weather (OpenWeather API)
3. Checks local events (manual entries or API)
4. Pulls historical revenue by location/day/weather
5. Location scoring algorithm runs
6. Results: "Courthouse: $892 predicted (jury duty Thursday)"
7. Owner gets SMS: "Recommended: Courthouse for Cart 1 tomorrow"
8. Owner replies "OK" or "DMV instead"
9. Assignment created in database
```

---

## Security Considerations

### Authentication
- Supabase Auth for user management
- JWT tokens with role claims
- Refresh token rotation

### Authorization
- Row-Level Security on all tables
- API-level permission checks
- Role-based UI rendering

### Data Protection
- HTTPS everywhere
- Encrypted at rest (Supabase default)
- WiFi MACs hashed before storage
- Photo URLs are signed, time-limited

### Operational Security
- Hardware ID verification for cart communications
- Webhook signature validation (Square, Twilio)
- Rate limiting on API endpoints

---

## Scaling Considerations

### Current Design Supports:
- 100+ organizations (tenants)
- 1,000+ carts
- 10,000+ transactions/day
- 50,000+ quality check photos

### If You Need More:
- Move to dedicated Supabase instance
- Add Redis for caching frequent queries
- Implement queue for webhook processing
- Consider read replicas for dashboard queries

---

## Development Setup

See [Setup Guide](../setup/README.md) for:
- Local development environment
- Database migrations
- API testing
- Frontend development
- Hardware simulation (for testing without Pi)

---

## Extending FoodCartOS

### Adding a New Integration

1. Create service in `app/services/`
2. Add router in `app/routers/`
3. Create n8n workflow for automation
4. Add frontend components as needed
5. Document in `docs/integrations/`

### Adding a New Feature

1. Design database schema changes
2. Create Supabase migration
3. Add API endpoints
4. Build n8n workflow (if automated)
5. Create frontend UI
6. Write tests
7. Document usage

---

*Architecture evolves. This document should be updated when significant changes are made.*
