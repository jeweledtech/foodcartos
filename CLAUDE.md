# CLAUDE.md - FoodCartOS Project Context

This file provides context for Claude Code when working on the FoodCartOS project.

## Project Overview

**FoodCartOS** is an open-source operating system for food cart entrepreneurs, helping them scale from 1-3 carts to multi-location operations while maintaining brand quality.

**First Customer:** EatFireCraft (Poncho's hot dog cart business in Vacaville, CA)

## The Core Problem We're Solving

Poncho was losing $19,760/year by going to the courthouse on Wednesdays ($510) instead of Thursdays ($890 - jury duty days). He didn't have the data to know this.

**Three key pain points:**
1. **Location blindness** - No data on which location/day combinations are profitable
2. **Employee trust** - Can't verify quality standards without being present
3. **Brand fear** - "I don't want the brand to water down"

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, Supabase (PostgreSQL)
- **Automation:** n8n workflows
- **Hardware:** Raspberry Pi 4, SIM7600A-H (cellular+GPS), camera
- **Frontend:** Mobile-first PWA (not yet built)
- **Integrations:** Square POS, Twilio SMS

## Key Files

| File | Purpose |
|------|---------|
| `docs/personas/README.md` | Deep customer psychology (Poncho's fears, hopes, quotes) |
| `docs/business-models/README.md` | 5 monetization strategies |
| `docs/case-studies/eatfirecraft.md` | Complete case study with ROI |
| `docs/session-logs/` | Detailed session logs for continuity |
| `app/routers/locations.py` | Core location intelligence feature |
| `app/routers/quality.py` | Photo verification system |

## Development Status

**Completed:**
- Project structure and documentation
- FastAPI routers (stub implementations)
- Database schema and RLS policies
- Business model documentation

**TODO:**
- [ ] Supabase service layer implementations
- [ ] Square webhook handlers (full implementation)
- [ ] n8n workflow JSON files
- [ ] Frontend PWA
- [ ] Hardware agent code for Raspberry Pi

## Design Principles

1. **Offline-first** - Carts have poor connectivity, must work without internet
2. **Simple UX** - "Big buttons, pictures, done" - food cart owners aren't tech people
3. **Quick value** - Show ROI in 2 weeks, not 6 months
4. **Brand protection** - Every feature should help maintain quality standards

## Key Quotes to Remember

> "I don't want the brand to water down." — Poncho (on his biggest fear)

> "Location is what stops me from cart #4." — Poncho (on growth blockers)

> "In two to five years, I'm going to be the new In-N-Out." — Poncho (on vision)

## Commands

```bash
# Run backend
python -m uvicorn app.main:app --reload

# Run tests
pytest

# Format code
black . && ruff check .
```

## Session Continuity

When continuing work on this project, reference:
1. This file (CLAUDE.md) - automatically loaded
2. `docs/session-logs/` - detailed session history
3. `docs/personas/README.md` - customer context

For business context, always consider: "Would Poncho understand this? Does it protect his brand quality?"
