# Contributing to FoodCartOS

Thank you for your interest in contributing to FoodCartOS! This project exists to help food cart entrepreneurs like Poncho scale their businesses while maintaining the quality that made them successful.

---

## Our Mission

> "I don't want the brand to water down." — Poncho, EatFireCraft

FoodCartOS helps food cart operators:
1. **Know their numbers** - Location intelligence, revenue tracking
2. **Trust their team** - Photo verification, quality scores
3. **Grow their brand** - SMS marketing, customer loyalty
4. **Scale to franchise** - Multi-operator dashboards, compliance

Every contribution should serve this mission.

---

## Ways to Contribute

### Code Contributions

- **Bug fixes** - Found something broken? Fix it!
- **New features** - Check the roadmap for planned features
- **Integrations** - Add support for new POS systems, SMS providers, etc.
- **Performance** - Make things faster, more reliable

### Documentation

- **Improve clarity** - Simplify confusing sections
- **Add examples** - Real-world usage examples help everyone
- **Translations** - Help non-English speakers
- **Tutorials** - Step-by-step guides for common tasks

### Design

- **UI improvements** - Make the dashboard more intuitive
- **Mobile optimization** - Food cart operators use phones, not desktops
- **Accessibility** - Ensure everyone can use FoodCartOS

### Testing

- **Manual testing** - Try features and report issues
- **Automated tests** - Improve test coverage
- **Real-world testing** - Run FoodCartOS on an actual cart!

### Community

- **Answer questions** - Help others in Discussions
- **Share your setup** - Document your implementation
- **Feedback** - Tell us what works and what doesn't

---

## Getting Started

### 1. Fork and Clone

```bash
# Fork via GitHub UI, then:
git clone https://github.com/YOUR_USERNAME/foodcartos.git
cd foodcartos
```

### 2. Set Up Development Environment

```bash
# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Testing tools

# Frontend
cd frontend
npm install
```

### 3. Run Tests

```bash
# Backend tests
pytest

# Frontend tests
cd frontend
npm test
```

### 4. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

---

## Development Guidelines

### Code Style

**Python (Backend)**
- Follow PEP 8
- Use type hints
- Format with Black: `black .`
- Lint with Ruff: `ruff check .`

```python
# Good
def get_location_performance(
    location_id: str,
    start_date: datetime,
    end_date: datetime
) -> LocationPerformance:
    """Calculate performance metrics for a location."""
    ...

# Bad
def get_perf(loc, start, end):
    ...
```

**TypeScript (Frontend)**
- Use TypeScript, not JavaScript
- Format with Prettier: `npm run format`
- Lint with ESLint: `npm run lint`

```typescript
// Good
interface LocationPerformance {
  locationId: string;
  averageRevenue: number;
  dayOfWeekPattern: Record<number, number>;
}

// Bad
const perf: any = { ... };
```

### Commit Messages

Use conventional commits:

```
feat: add weather impact to location scoring
fix: prevent duplicate SMS notifications
docs: add hardware installation troubleshooting
refactor: simplify transaction sync logic
test: add tests for pre-order workflow
```

### Pull Request Process

1. **Create focused PRs** - One feature/fix per PR
2. **Write a clear description** - What, why, and how
3. **Link related issues** - "Fixes #123"
4. **Add tests** - For new features and bug fixes
5. **Update documentation** - If behavior changes
6. **Request review** - Tag relevant maintainers

### PR Template

```markdown
## What does this PR do?
[Brief description]

## Why is this needed?
[Explain the problem or feature request]

## How does it work?
[Technical explanation]

## How was it tested?
- [ ] Unit tests pass
- [ ] Manual testing done
- [ ] Tested on real hardware (if applicable)

## Screenshots (if UI changes)
[Before/after screenshots]

## Related Issues
Fixes #[issue number]
```

---

## Architecture Decisions

### When to Discuss First

Open a Discussion or Issue before working on:
- New integrations (POS systems, etc.)
- Database schema changes
- Breaking API changes
- Major UI redesigns
- New dependencies

### Design Principles

**1. Offline-First**
Food carts often have poor connectivity. Features must work offline and sync when possible.

```python
# Good: Store locally, sync later
def record_transaction(transaction):
    local_db.insert(transaction)
    sync_queue.add(transaction)

# Bad: Require internet
def record_transaction(transaction):
    cloud_db.insert(transaction)  # Fails without internet!
```

**2. Simple UX**
Our users aren't tech people. They're making hot dogs.

> "Big buttons, pictures, done."

```typescript
// Good: Clear, visual
<Button size="xl" icon={<CameraIcon />}>
  Take Photo
</Button>

// Bad: Technical
<input type="file" accept="image/*" onChange={handleFileUpload} />
```

**3. Quick Value**
Show value in the first 2 weeks, not 6 months.

```python
# Good: Immediate insight
def get_quick_wins(org_id):
    """Find money-saving opportunities with minimal data."""
    # Works with just 1 week of data
    ...

# Bad: Requires months of data
def get_predictions(org_id):
    if data_points < 1000:
        raise InsufficientDataError()
```

**4. Protect the Brand**
Every feature should help maintain quality standards.

```python
# Good: Enforces quality check
def start_shift(employee_id, cart_id):
    if not all_photos_uploaded(employee_id, cart_id):
        raise ShiftNotAllowed("Complete quality checklist first")

# Bad: Skippable
def start_shift(employee_id, cart_id):
    # Just let them start
    ...
```

---

## Testing Requirements

### Unit Tests

All new code should have tests:

```python
# tests/test_location_scoring.py
def test_jury_duty_bonus():
    """Thursday courthouse should score 74% higher."""
    thursday_score = score_location("courthouse", thursday, good_weather)
    wednesday_score = score_location("courthouse", wednesday, good_weather)

    assert thursday_score > wednesday_score * 1.7
```

### Integration Tests

For API endpoints and workflows:

```python
# tests/test_api.py
async def test_transaction_webhook():
    """Square webhook should create transaction record."""
    response = await client.post(
        "/webhooks/square",
        json=SAMPLE_SQUARE_WEBHOOK,
        headers={"X-Square-Signature": valid_signature}
    )

    assert response.status_code == 200
    assert await db.transaction_exists(SAMPLE_SQUARE_WEBHOOK["id"])
```

### Hardware Testing

If your change affects hardware:
- Test on actual Raspberry Pi (not just x86)
- Test with cellular connection
- Test offline → online sync
- Document any hardware-specific issues

---

## Documentation Standards

### Code Comments

```python
# Good: Explains WHY
# Jury duty days have 74% higher revenue based on
# 6 months of EatFireCraft courthouse data
JURY_DUTY_MODIFIER = 1.74

# Bad: Explains WHAT (obvious from code)
# Multiply by 1.74
score = base * 1.74
```

### README Updates

If you add a feature, update relevant docs:
- Main README.md if it's a major feature
- Specific guide in docs/ for detailed usage
- API reference if endpoints change

### Examples

Include real-world examples:

```python
# Example: Calculate location recommendation
from foodcartos import LocationScorer

scorer = LocationScorer(org_id="eatfirecraft")

# Get tomorrow's recommendations
recommendations = scorer.get_recommendations(
    date=datetime.now() + timedelta(days=1),
    carts=["cart_1", "cart_2", "cart_3"]
)

# Result:
# [
#     {"cart": "cart_1", "location": "courthouse", "predicted_revenue": 890},
#     {"cart": "cart_2", "location": "dmv", "predicted_revenue": 620},
#     ...
# ]
```

---

## Community Guidelines

### Be Kind

Remember: We're building this to help real people like Poncho grow their businesses. Treat everyone with respect.

### Be Patient

Food cart owners aren't developers. When someone asks a "basic" question, answer helpfully.

### Be Constructive

In code reviews:
- Explain WHY, not just what to change
- Offer alternatives, not just criticism
- Acknowledge good work

### Be Inclusive

- Use clear language (not everyone speaks English natively)
- Consider accessibility in UI contributions
- Welcome newcomers warmly

---

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes for significant contributions
- Annual contributor spotlight posts

---

## Questions?

- **Technical questions:** Open a Discussion
- **Bug reports:** Open an Issue
- **Feature ideas:** Open a Discussion first
- **Security issues:** Email security@foodcartos.org (don't open public issues)

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

*Thank you for helping food cart entrepreneurs succeed!*
