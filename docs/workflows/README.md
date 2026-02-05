# FoodCartOS n8n Workflows

This guide covers the automation workflows that power FoodCartOS. These workflows handle everything from morning checklists to SMS marketing to daily revenue reports.

**Why n8n?**
- Visual workflow builder (non-developers can modify)
- Self-hostable (control your data)
- Large library of integrations
- Affordable at scale

---

## Core Workflows

### 1. Morning Checklist Verification

**Purpose:** Ensure employees complete quality checks before shift starts.

**Trigger:** Quality check photo uploaded

**Flow:**
```
┌──────────────────┐
│ Webhook: Photo   │
│ Uploaded         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Check: All       │
│ required photos? │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────────┐
│ YES    │ │ NO         │
└───┬────┘ └─────┬──────┘
    │            │
    ▼            ▼
┌────────────┐ ┌────────────────┐
│ Mark shift │ │ Wait 30 min    │
│ started    │ │ then alert     │
└────────────┘ │ owner          │
               └────────────────┘
```

**Configuration:**

```json
{
  "required_checks": [
    "dirty_water_setup",
    "garlic_butter_prep",
    "cart_display"
  ],
  "deadline_minutes": 30,
  "alert_channel": "sms",
  "owner_phone": "+1234567890"
}
```

**Customization points:**
- Add/remove required check types
- Adjust deadline
- Change alert method (SMS, Slack, email)

---

### 2. Daily Revenue Summary

**Purpose:** Send owner a summary of the day's performance every evening.

**Trigger:** Cron (9 PM daily)

**Flow:**
```
┌──────────────────┐
│ Cron: 9 PM       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Fetch today's    │
│ transactions     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Group by cart    │
│ and location     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Compare to       │
│ historical avg   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Format message   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Send SMS to      │
│ owner            │
└──────────────────┘
```

**Sample output:**

```
📊 EatFireCraft Daily Summary

Today: $1,847 across 3 carts

Cart 1 (Courthouse): $892 ⬆️ +12%
Cart 2 (DMV): $610 ⬇️ -8%
Cart 3 (Downtown): $345 ➡️ avg

Top performer: Cart 1
Recommendation: Move Cart 2 to Sheriff's Office tomorrow

Week to date: $4,231 / $5,000 goal (85%)
```

**Configuration:**

```json
{
  "send_time": "21:00",
  "timezone": "America/Los_Angeles",
  "include_recommendations": true,
  "compare_period": "30_days"
}
```

---

### 3. Location Recommendations

**Purpose:** Suggest optimal cart placements for the next day.

**Trigger:** Cron (6 AM daily)

**Flow:**
```
┌──────────────────┐
│ Cron: 6 AM       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Get tomorrow's   │
│ weather forecast │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Check local      │
│ events calendar  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Pull historical  │
│ revenue by       │
│ location/day     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Run scoring      │
│ algorithm        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Generate ranked  │
│ recommendations  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Send to owner    │
│ for approval     │
└──────────────────┘
```

**Sample output:**

```
🗓️ Tomorrow's Plan (Thursday)

Cart 1 Recommendation: COURTHOUSE
├── Predicted revenue: $890
├── Reason: Jury duty day (+74% vs avg)
├── Weather: Clear, 72°F
└── Confidence: HIGH

Cart 2 Recommendation: DMV
├── Predicted revenue: $620
├── Reason: Second-best Thursday location
├── Weather: Good
└── Confidence: MEDIUM

Cart 3 Recommendation: DOWNTOWN
├── Predicted revenue: $480
├── Reason: Farmers market nearby
└── Confidence: MEDIUM

Reply OK to confirm, or specify changes.
```

**Location Scoring Algorithm:**

```python
def score_location(location, date, weather):
    # Base score from historical average
    base = get_historical_avg(location, date.weekday())

    # Day-of-week modifier
    dow_modifier = get_dow_pattern(location, date.weekday())

    # Weather impact
    weather_modifier = calculate_weather_impact(weather)
    # Rain: -30%, Hot (>90°F): +15%, Cold (<50°F): -20%

    # Event bonus
    event_modifier = check_local_events(location, date)
    # Jazz festival: +40%, Jury duty: +74%

    # Calculate final score
    score = base * dow_modifier * weather_modifier * event_modifier

    # Confidence based on data availability
    confidence = calculate_confidence(location, date)

    return {
        "score": score,
        "confidence": confidence,
        "factors": [dow_modifier, weather_modifier, event_modifier]
    }
```

---

### 4. SMS Marketing: Location Alerts

**Purpose:** Notify opted-in customers when a cart arrives at a location.

**Trigger:** GPS geofence entered

**Flow:**
```
┌──────────────────┐
│ GPS: Cart        │
│ entered geofence │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Identify         │
│ location         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Get subscribers  │
│ for this location│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Check last       │
│ message time     │
│ (prevent spam)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Format message   │
│ with today's     │
│ special          │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Send via Twilio  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Log delivery     │
│ for analytics    │
└──────────────────┘
```

**Sample messages:**

```
🌭 EatFireCraft is at the DMV!

Open until 2 PM today.
Today's special: Brisket dog $14

Reply STOP to unsubscribe
```

```
🌭 Find us at the Courthouse!

Serving 11 AM - 3 PM
Try our famous garlic butter bun

Reply ORDER to pre-order (ready in 10 min)
```

**Configuration:**

```json
{
  "geofence_radius_meters": 100,
  "min_hours_between_messages": 24,
  "include_special": true,
  "enable_pre_orders": true,
  "message_template": "🌭 {brand} is at {location}!\n\nOpen until {close_time}.\n{special_line}\n\nReply STOP to unsubscribe"
}
```

---

### 5. Pre-Order Handler

**Purpose:** Process customer pre-orders received via SMS.

**Trigger:** Incoming SMS with "ORDER" keyword

**Flow:**
```
┌──────────────────┐
│ Twilio webhook:  │
│ SMS received     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Parse message    │
│ for intent       │
└────────┬─────────┘
         │
    ┌────┴────┬────────┐
    │         │        │
    ▼         ▼        ▼
┌────────┐ ┌────────┐ ┌────────┐
│ ORDER  │ │ STOP   │ │ Other  │
└───┬────┘ └───┬────┘ └───┬────┘
    │          │          │
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│ Look up│ │ Unsub- │ │ Send   │
│ last   │ │ scribe │ │ menu   │
│ order  │ │ user   │ │ options│
└───┬────┘ └────────┘ └────────┘
    │
    ▼
┌──────────────────┐
│ Send confirm     │
│ with ETA         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Alert cart       │
│ operator         │
└──────────────────┘
```

**Sample conversation:**

```
Customer: ORDER

Bot: 🌭 What would you like?
     1. Classic Dog $8
     2. Dirty Water Dog $10
     3. Brisket Dog $14
     Reply with number or "same" for your usual

Customer: same

Bot: ✅ 2x Dirty Water Dogs confirmed!
     Ready in 10 minutes at DMV location
     Total: $20 (pay at cart)
```

---

### 6. Employee Performance Alert

**Purpose:** Alert owner when quality metrics fall below threshold.

**Trigger:** Quality score calculated (daily)

**Flow:**
```
┌──────────────────┐
│ Daily quality    │
│ score calculated │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Check against    │
│ threshold (80%)  │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────────┐
│ PASS   │ │ FAIL       │
│ (≥80%) │ │ (<80%)     │
└────────┘ └─────┬──────┘
                 │
                 ▼
          ┌──────────────┐
          │ Check if     │
          │ repeat issue │
          └──────┬───────┘
                 │
            ┌────┴────┐
            │         │
            ▼         ▼
       ┌────────┐ ┌────────────┐
       │ First  │ │ Repeat     │
       │ time   │ │ (3+ days)  │
       └───┬────┘ └─────┬──────┘
           │            │
           ▼            ▼
       ┌────────┐ ┌────────────┐
       │ Log    │ │ ALERT      │
       │ warning│ │ owner      │
       └────────┘ └────────────┘
```

**Sample alert:**

```
⚠️ Employee Performance Alert

Cart 2 (Brother-in-law) has scored below 80% for 3 consecutive days.

Quality scores:
- Mon: 67% (missing garlic butter photo)
- Tue: 73% (late check-in)
- Wed: 60% (2 missing photos)

Suggested action: Schedule training conversation

View details: [dashboard link]
```

---

## Workflow Templates

All workflow JSON files are in the `workflows/` directory:

```
workflows/
├── core/
│   ├── morning-checklist.json
│   ├── daily-revenue-summary.json
│   ├── location-recommendations.json
│   └── employee-performance-alert.json
├── marketing/
│   ├── location-arrival-alert.json
│   ├── pre-order-handler.json
│   ├── loyalty-program.json
│   └── weekly-special-blast.json
├── operations/
│   ├── inventory-low-alert.json
│   ├── weather-impact-alert.json
│   └── event-reminder.json
└── admin/
    ├── new-employee-onboarding.json
    ├── monthly-report-generator.json
    └── franchise-compliance-check.json
```

---

## Creating Custom Workflows

### Step 1: Identify the Trigger

Common triggers in FoodCartOS:

| Trigger | Use Case |
|---------|----------|
| Webhook | Real-time events (photo upload, transaction) |
| Cron | Scheduled tasks (daily reports, morning alerts) |
| Database change | Supabase realtime (new record, update) |
| SMS received | Customer interactions |
| GPS geofence | Location-based automation |

### Step 2: Map the Logic

Use n8n's visual builder to:
1. Add trigger node
2. Add data fetch nodes (Supabase, HTTP)
3. Add logic nodes (IF, Switch)
4. Add action nodes (Twilio, Slack, HTTP)

### Step 3: Test with Sample Data

1. Use n8n's "Execute" button with test data
2. Check each node's output
3. Verify final action (message sent, record created)

### Step 4: Activate and Monitor

1. Toggle workflow to Active
2. Monitor executions in n8n
3. Set up error notifications

---

## Best Practices

### 1. Error Handling

Always add error handling nodes:

```
┌──────────┐
│ Main     │
│ flow     │
└────┬─────┘
     │
     ├───────────────┐
     │               │
     ▼               ▼
┌─────────┐    ┌─────────────┐
│ Success │    │ Error       │
│ path    │    │ handler     │
└─────────┘    └──────┬──────┘
                      │
                      ▼
               ┌─────────────┐
               │ Log error + │
               │ notify team │
               └─────────────┘
```

### 2. Rate Limiting

For SMS workflows:
- Track last message time per customer
- Minimum 24 hours between automated messages
- Maximum 4 messages per week

### 3. Personalization

Use customer data for better messages:

```javascript
// Good
`Hi ${customer.first_name}! Your usual (${customer.last_order}) is ready in 10 min.`

// Bad
`Your order is ready.`
```

### 4. Testing

Before activating:
1. Test with your own phone number
2. Verify all edge cases
3. Check message formatting
4. Confirm data flows correctly

### 5. Monitoring

Set up alerts for:
- Workflow execution failures
- Unusual patterns (too many/few executions)
- API errors (Twilio, Square, etc.)

---

## Workflow Pricing (n8n)

### Self-hosted
- Free (unlimited executions)
- Requires server ($5-20/month VPS)
- You manage updates and maintenance

### n8n Cloud

| Plan | Price | Executions | Best For |
|------|-------|------------|----------|
| Starter | $20/mo | 2,500 | 1-2 carts |
| Pro | $50/mo | 10,000 | 3-10 carts |
| Enterprise | Custom | Unlimited | 10+ carts |

**Execution estimate per cart:**
- Morning checklist: 3/day
- Revenue summary: 1/day
- Location alerts: 5/day
- Pre-orders: 10/day
- **Total: ~20/day = 600/month per cart**

---

## Next Steps

1. [Import core workflows](./importing-workflows.md)
2. [Configure credentials](./credentials-setup.md)
3. [Customize for your brand](./customization.md)
4. [Build custom workflows](./custom-workflows.md)
