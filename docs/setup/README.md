# FoodCartOS Setup Guide

This guide walks you through setting up FoodCartOS from scratch. Whether you're setting up for yourself or deploying for a client, follow these steps.

**Time required:** 2-4 hours for software, 1-2 hours for hardware installation

---

## Prerequisites

### Software Requirements
- Python 3.11+
- Node.js 18+
- Docker (optional, for local development)
- Git

### Accounts Needed
- [Supabase](https://supabase.com) - Free tier works for development
- [Square Developer](https://developer.squareup.com) - For POS integration
- [Twilio](https://twilio.com) - For SMS ($50+ credit recommended)
- [n8n Cloud](https://n8n.io) or self-hosted n8n

### Hardware (for cart installation)
- Raspberry Pi 4 (4GB+ RAM)
- SIM7600A-H HAT
- T-Mobile IoT SIM card
- Camera module
- 7" touchscreen (optional)
- ESP32-S3 XIAO (optional, for foot traffic)

---

## Part 1: Backend Setup

### Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/yourusername/foodcartos.git
cd foodcartos

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# Square
SQUARE_ACCESS_TOKEN=your-square-token
SQUARE_LOCATION_ID=your-location-id
SQUARE_WEBHOOK_SIGNATURE_KEY=your-webhook-key

# Twilio
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# Weather (optional)
OPENWEATHER_API_KEY=your-api-key

# App Settings
APP_ENV=development
API_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
```

### Step 3: Set Up Supabase

1. Create a new Supabase project
2. Go to SQL Editor and run the migrations:

```bash
# From project root
psql $SUPABASE_DB_URL < migrations/001_initial_schema.sql
psql $SUPABASE_DB_URL < migrations/002_row_level_security.sql
psql $SUPABASE_DB_URL < migrations/003_functions.sql
```

Or use the Supabase CLI:

```bash
supabase db push
```

3. Enable Row Level Security on all tables (should be automatic from migrations)

4. Create storage bucket for photos:
   - Go to Storage in Supabase dashboard
   - Create bucket named `quality-photos`
   - Set policy to allow authenticated uploads

### Step 4: Run the Backend

```bash
# Development server with auto-reload
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or with Docker
docker-compose up api
```

Verify it's working:
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

---

## Part 2: Square Integration

### Step 1: Create Square Application

1. Go to [Square Developer Dashboard](https://developer.squareup.com)
2. Create new application
3. Get your **Access Token** from Credentials
4. Note your **Location ID** from Locations

### Step 2: Configure Webhooks

In Square Developer Dashboard:
1. Go to Webhooks
2. Add webhook endpoint: `https://your-domain.com/webhooks/square`
3. Subscribe to events:
   - `payment.completed`
   - `payment.updated`
   - `refund.created`
4. Copy the **Signature Key** to your `.env`

### Step 3: Test the Integration

```bash
# Fetch locations (verifies API key works)
curl http://localhost:8000/api/square/locations

# Create a test transaction in Square
# Then check it appears in your database
curl http://localhost:8000/api/transactions
```

---

## Part 3: n8n Workflows

### Step 1: Set Up n8n

**Option A: n8n Cloud (Recommended for production)**
1. Sign up at [n8n.io](https://n8n.io)
2. Get your instance URL (e.g., `https://your-name.app.n8n.cloud`)

**Option B: Self-hosted**
```bash
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

### Step 2: Import Core Workflows

Import the workflows from `workflows/` directory:

1. Open n8n dashboard
2. Go to Workflows → Import
3. Import each JSON file:
   - `morning-checklist.json`
   - `daily-revenue-summary.json`
   - `location-recommendations.json`
   - `sms-marketing.json`

### Step 3: Configure Credentials in n8n

Create credentials for:
- **Supabase:** API key and URL
- **Twilio:** Account SID and Auth Token
- **HTTP:** For calling your FastAPI backend

### Step 4: Activate Workflows

1. Open each workflow
2. Update any hardcoded values (org_id, phone numbers, etc.)
3. Toggle the workflow to Active
4. Test with manual trigger

---

## Part 4: Frontend Setup

### Step 1: Install Dependencies

```bash
cd frontend
npm install
```

### Step 2: Configure Environment

```bash
cp .env.example .env.local
```

Edit `.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Step 3: Run Development Server

```bash
npm run dev
```

Visit `http://localhost:3000`

### Step 4: Create First User

1. Go to the registration page
2. Create an owner account
3. Verify email (check Supabase Auth logs if email not received)
4. Log in and complete organization setup

---

## Part 5: Hardware Installation (Cart Setup)

See [Hardware Guide](../hardware/README.md) for detailed instructions.

### Quick Overview:

1. **Prepare Raspberry Pi**
   ```bash
   # Flash Raspberry Pi OS Lite (64-bit)
   # Enable SSH, set WiFi for initial setup
   ```

2. **Install FoodCartOS Agent**
   ```bash
   ssh pi@your-pi-ip
   curl -fsSL https://raw.githubusercontent.com/yourusername/foodcartos/main/hardware/install.sh | bash
   ```

3. **Configure SIM7600A-H**
   - Attach HAT to Pi
   - Insert T-Mobile IoT SIM
   - Run cellular setup script

4. **Connect Hardware**
   - Camera module
   - Touchscreen (optional)
   - ESP32-S3 (optional)

5. **Register Cart**
   - Run registration script
   - Links hardware ID to your organization

---

## Part 6: First Run Checklist

### Backend
- [ ] API responds to `/health`
- [ ] Database tables created
- [ ] Row Level Security enabled
- [ ] Storage bucket created

### Square
- [ ] Can fetch locations via API
- [ ] Webhook endpoint reachable
- [ ] Test transaction appears in database

### n8n
- [ ] All workflows imported
- [ ] Credentials configured
- [ ] Workflows activated
- [ ] Test SMS sends successfully

### Frontend
- [ ] Can log in as owner
- [ ] Dashboard loads
- [ ] Can create locations
- [ ] Can register carts

### Hardware (if applicable)
- [ ] Pi boots and connects to internet
- [ ] GPS reports location
- [ ] Camera takes photos
- [ ] Local database syncs to cloud

---

## Troubleshooting

### "Cannot connect to Supabase"
- Check `SUPABASE_URL` doesn't have trailing slash
- Verify `SUPABASE_ANON_KEY` is correct (not service key for frontend)
- Check Supabase project is running (not paused)

### "Square webhook not receiving"
- Verify webhook URL is publicly accessible
- Check signature key matches
- Look at Square webhook logs for errors

### "SMS not sending"
- Verify Twilio credentials
- Check phone number format (+1 prefix for US)
- Verify Twilio has sufficient balance
- Check Twilio console for error logs

### "Pi not syncing"
- Check cellular signal (AT commands)
- Verify API endpoint is reachable from Pi
- Check SQLite database for unsynced records
- Look at Pi logs: `journalctl -u foodcartos-agent`

---

## Next Steps

1. [Configure your first location](./locations.md)
2. [Set up employee accounts](./employees.md)
3. [Create morning checklist](./quality-checks.md)
4. [Configure SMS marketing](./sms-marketing.md)

---

## Support

- **Issues:** GitHub Issues
- **Questions:** GitHub Discussions
- **Community:** Discord

*Need help with a client installation? See [Business Models](../business-models/README.md) for service offerings.*
