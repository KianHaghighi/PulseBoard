# PulseBoard

Market research and startup intelligence platform. Aggregates news, SEC financial data, and VC firm profiles into a single feed — with AI-powered summaries, personalized filtering, and a daily email digest.

## Features

- **Private Markets feed** — RSS + NewsAPI ingestion (TechCrunch, VentureBeat, The Information, Sifted), updated every 30 minutes
- **Filter by source, category, or keyword** — pill filters for news sources; category tags (AI & ML, Funding, Startups, etc.); "For You" sort based on saved keywords
- **AI summaries** — on-demand article summarization via Claude Haiku
- **Collections** — save articles to named collections; create/delete collections from your profile
- **Public Markets tab** — SEC EDGAR financials (revenue, net income, EPS, assets) + ATS job posting counts for public tech companies
- **VC Funding Finder** — browse 25+ major VC firms; AI thesis matching sends your startup description to Claude and returns ranked firm matches with reasoning
- **Daily email digest** — SendGrid digest of top articles matching your keywords, sent at 08:00 UTC
- **Auth** — Auth0 OAuth login; guest users can browse the feed without an account
- **Admin panel** — user list, article count, manual ingest trigger, article deletion

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Flask (Python) |
| Frontend | Jinja2 templates |
| Database | PostgreSQL + SQLAlchemy |
| Auth | Auth0 (authlib) |
| News ingestion | feedparser + NewsAPI |
| AI | Anthropic Claude Haiku |
| Email | SendGrid |
| Scheduler | APScheduler |
| SEC data | EDGAR XBRL API |

## Setup

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd new_proj
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in values:

```
SECRET_KEY=<random-string>
DATABASE_URL=postgresql://localhost/pulseboard
AUTH0_DOMAIN=<your-tenant>.auth0.com
AUTH0_CLIENT_ID=<client-id>
AUTH0_CLIENT_SECRET=<client-secret>
AUTH0_CALLBACK_URL=http://localhost:5000/auth/callback
NEWS_API_KEY=<newsapi.org key>
ANTHROPIC_API_KEY=<anthropic key>
SENDGRID_API_KEY=<sendgrid key>
MAIL_FROM=digest@pulseboard.io
```

### 3. Create the database

```bash
createdb pulseboard
```

### 4. Run

```bash
python run.py
```

The app starts at `http://127.0.0.1:5000`. On first boot it creates all tables, seeds public company and VC firm data, and begins the background scheduler.

## Project Structure

```
app/
├── __init__.py          # App factory + APScheduler (ingest 30 min, EDGAR/jobs/digest 24 h)
├── config.py
├── extensions.py
├── models/models.py     # User, Article, Like, Collection, CollectionItem,
│                        # PublicCompany, FinancialSnapshot, JobPostingCount, VCFirm
├── routes/
│   ├── feed.py          # /, /like, /save, /summarize
│   ├── auth.py          # /auth/login, /callback, /logout
│   ├── profile.py       # /profile/ — collections + settings
│   ├── admin.py         # /admin/ — user list, manual ingest
│   ├── public_markets.py# /public/ — SEC financials + job counts
│   └── vc.py            # /vc/ — firm browser + AI thesis matcher
├── services/
│   ├── ingestion.py     # ingest_rss(), ingest_newsapi()
│   ├── summarizer.py    # summarize_article(), tag_category() via Claude
│   ├── digest.py        # send_daily_digest() via SendGrid
│   ├── edgar.py         # SEC EDGAR financials
│   ├── jobs.py          # ATS job posting counts
│   ├── thesis.py        # AI VC thesis matching
│   └── vc_data.py       # VC firm seed data (25 firms)
└── templates/
    ├── base.html
    ├── feed/index.html
    ├── public/          # Public markets table + company detail
    ├── vc/              # VC browser + firm profile
    ├── profile/         # Collections, settings
    ├── admin/
    └── email/digest.html
```

## Running Tests

```bash
pytest tests/
```
