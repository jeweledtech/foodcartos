# FoodCartOS

**The Open-Source Operating System for Food Cart Entrepreneurs**

FoodCartOS helps food cart operators scale from 1-3 carts to multi-location operations (and eventually franchises) while maintaining brand quality, financial transparency, and employee accountability.

## Why This Exists

We built this for Poncho.

Poncho runs EatFireCraft, a hot dog cart business in Vacaville, California. He makes ~$5,000/week across 3 carts with his signature dirty water dogs and garlic butter buns. His customers love him. His brand is growing.

But he's stuck.

> "Location is what stops me from cart #4."

> "I don't want the brand to water down."

> "I need employees in locations to be able to do this... but I can't be putting butter on buns. Someone else needs to do that."

He's been going to the courthouse on Wednesdays ($510/day) when Thursdays (jury duty days) hit $890. That's $380 lost every week because he didn't have the data.

He hired his brother-in-law but can't verify if the garlic butter prep is happening correctly. He's scared of hiring because previous partners "watered down the brand."

**FoodCartOS solves these problems.**

## What It Does

### Phase 1: Know Your Numbers
- Square POS integration for real-time revenue tracking
- Location-based performance analysis
- Day-of-week and weather pattern insights
- "You're losing $380/week by being at the wrong location"

### Phase 2: Trust Your Team
- Morning checklist with photo verification
- Employees prove they set up the dirty water correctly
- Quality scores and performance leaderboards
- If the photo isn't uploaded, the shift doesn't count

### Phase 3: Grow Your Brand
- SMS marketing to loyal customers
- "Find us today at [location]" automated alerts
- Pre-order system via text
- Social media automation for location announcements

### Phase 4: Scale to Franchise
- Multi-operator dashboards
- Franchisee portals with brand compliance tracking
- Revenue split calculations
- Training system with video SOPs

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/foodcartos.git
cd foodcartos

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Configure your integrations (see docs/setup/)
# - Square API credentials
# - Supabase connection
# - Twilio for SMS

# Run the development server
python -m uvicorn app.main:app --reload
```

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture Overview](docs/architecture/README.md) | System design and tech stack |
| [Setup Guide](docs/setup/README.md) | Step-by-step installation |
| [Hardware Guide](docs/hardware/README.md) | Raspberry Pi, sensors, cameras |
| [Business Models](docs/business-models/README.md) | How to monetize FoodCartOS |
| [Customer Personas](docs/personas/README.md) | Understanding your customers |
| [n8n Workflows](docs/workflows/README.md) | Automation templates |
| [API Reference](docs/api/README.md) | REST API documentation |

## The Business Opportunity

FoodCartOS isn't just software—it's a business platform. See [Business Models](docs/business-models/README.md) for 5 ways to generate $10K+/month:

1. **Done-For-You Setups** ($1,500-$15,000 per client)
2. **Workflow Templates** ($197-$997 per sale)
3. **Consulting Multiplier** (4x your client capacity)
4. **Managed Service** ($497-$1,997/month recurring)
5. **Courses & Education** ($47-$997 per product)

## Tech Stack

- **Backend**: Python 3.11+, FastAPI
- **Database**: Supabase (PostgreSQL) + SQLite for offline
- **Automation**: n8n workflows
- **Hardware**: Raspberry Pi 4, SIM7600A-H cellular, ESP32-S3 WiFi scanner
- **Frontend**: Mobile-first PWA
- **Integrations**: Square POS, Twilio SMS, social media APIs

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Priority areas:**
- [ ] Square POS webhook handlers
- [ ] Location scoring algorithm
- [ ] Photo verification pipeline
- [ ] SMS marketing workflows
- [ ] Mobile dashboard UI

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/foodcartos/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/foodcartos/discussions)
- **Discord**: [Join our community](https://discord.gg/foodcartos)

---

*"In two to five years, I'm going to be the new In-N-Out."* — Poncho, EatFireCraft

FoodCartOS is the technology that makes visions like Poncho's possible.
