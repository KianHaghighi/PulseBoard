# PulseBoard — Development Plan

> Market Research & Startup Intelligence Platform  
> Based on PRD v0.2 | Updated 2026-05-30

---

## Tech Stack (Decided)

| Layer | Choice |
|---|---|
| Backend | Flask (Python) |
| Frontend | Jinja2 templates (server-side) |
| Database | PostgreSQL + SQLAlchemy |
| Auth | Auth0 (authlib) |
| News ingestion | feedparser (RSS) + NewsAPI |
| AI summarization / tagging | Anthropic Claude (Haiku 4.5) |
| Email digest | SendGrid |
| Job data | ATS scraping via `jobs.py` |
| SEC filings | EDGAR API via `edgar.py` |
| Hosting | TBD — Render / Railway / DigitalOcean |

---

## Phase 1 — MVP (Weeks 1–8)

### Week 1–2: Project Setup, Auth, DB, Ingestion

- [x] Flask app factory (`app/__init__.py`)
- [x] Config with env vars (`app/config.py`)
- [x] SQLAlchemy extensions (`app/extensions.py`)
- [x] DB models: `User`, `Article`, `Like`, `Collection`, `CollectionItem`
- [x] Auth0 login / callback / logout routes (`app/routes/auth.py`)
- [x] RSS ingestion — TechCrunch, VentureBeat, The Information, Sifted (`app/services/ingestion.py`)
- [x] NewsAPI ingestion (`app/services/ingestion.py`)
- [x] `.env.example` and `.gitignore`
- [x] Wire `init_oauth()` into app factory (`app/__init__.py`)
- [x] Add APScheduler — `_start_scheduler()` runs ingestion every 30 min (`app/__init__.py`)
- [x] Populate `requirements.txt` with all deps

### Week 3–4: Feed UI, Filtering, Search, Like/Dislike

- [x] Feed route with pagination, search, category filter, sort by recent/popular (`app/routes/feed.py`)
- [x] Like/dislike endpoint with toggle logic (`/like/<id>`)
- [x] Save-to-collection endpoint (`/save/<id>`)
- [x] Base template + feed template (`app/templates/`)
- [x] Article category auto-tagging via Claude Haiku (`tag_category()` in `app/services/summarizer.py`) — called during both RSS and NewsAPI ingestion; categories: AI & ML, Funding, Startups, Enterprise, Crypto & Web3, Policy, Science, Other
- [x] Keyword-based "For You" feed sort — filters articles by `current_user.keywords` (`app/routes/feed.py`)
- [x] Guest access — feed browsable without login; like/save/summarize require auth

### Week 5–6: Bookmarking, Collections, AI Summaries

- [x] Collection and CollectionItem models
- [x] Save article to collection endpoint
- [x] AI summarization via Anthropic Claude Haiku (`app/services/summarizer.py`)
- [x] On-demand summarize endpoint (`/summarize/<id>`)
- [x] Profile / collection view templates
- [x] Profile route: view collections, manage keywords, toggle digest (`app/routes/profile.py`)
- [x] Create / delete collection UI
- [x] Remove article from collection

### Week 7–8: Email Digest, Admin Panel, Polish, Beta

- [x] Daily digest service with SendGrid (`app/services/digest.py`)
- [x] Digest email template (`app/templates/email/digest.html`)
- [x] Admin blueprint registered
- [x] Admin route: list users, trigger manual ingest, view article count (`app/routes/admin.py`)
- [x] Scheduler to fire `send_daily_digest()` nightly (cron: 08:00 UTC)
- [x] User settings page: save keywords, toggle digest on/off
- [x] Mobile-responsive CSS pass
- [ ] `run.py` working end-to-end with a real DB connection
- [ ] Beta test with real Auth0 credentials + live DB

---

## Phase 1.5 — Public Markets Tab (Complete)

> Added after MVP scope. Surfaces SEC financial data and job-posting signals for public tech companies.

- [x] `PublicCompany` model — ticker, CIK, sector, last-refreshed timestamp (`app/models/models.py`)
- [x] `FinancialSnapshot` model — annual + quarterly revenue, net income, EPS, assets, cash (`app/models/models.py`)
- [x] `JobPostingCount` model — daily ATS snapshot per company; linked to `PublicCompany` or standalone by name (`app/models/models.py`)
- [x] EDGAR service: `seed_companies()`, `refresh_all()` — fetches SEC XBRL financials (`app/services/edgar.py`)
- [x] Jobs service: `get_latest_count()`, `get_mom_change()`, `refresh_all_jobs()` — scrapes ATS job boards (`app/services/jobs.py`)
- [x] APScheduler jobs for 24 h EDGAR refresh and 24 h jobs refresh (`app/__init__.py`)
- [x] Public Markets blueprint at `/public` (`app/routes/public_markets.py`)
  - Index: company table with latest revenue, YoY growth %, job count, MoM job change
  - Company detail: annual (4 yr) + quarterly (8 qtr) financial history + 30-day job posting chart
  - `/refresh` POST: paid-users-only manual EDGAR trigger
- [x] Template filters: `fmt_money`, `fmt_eps`, `fmt_pct`
- [x] Templates: `app/templates/public/index.html`, `app/templates/public/company.html`

---

## Phase 1.5 — VC Funding Finder Tab (Complete)

> Added after MVP scope. Helps founders discover matching VC firms via AI thesis analysis.

- [x] `VCFirm` model — name, description, website, HQ city, founded year, focus sectors, stages, check range ($K), AUM, notable portfolio (`app/models/models.py`)
- [x] VC seed data: 25 major firms (YC, a16z, Sequoia, Benchmark, Accel, etc.) auto-loaded on startup (`app/services/vc_data.py`)
- [x] VC blueprint at `/vc` (`app/routes/vc.py`)
  - Index: browseable firm list with stage and keyword filters
  - Firm detail: firm profile + live job count for each portfolio company
  - `/thesis` POST: AI-powered thesis matching endpoint
- [x] Thesis analysis service (`app/services/thesis.py`) — sends founder thesis to Claude, returns ranked VC matches with reasoning + relevant article matches
- [x] Template filter: `fmt_check_k` (formats $K values as $K / $M)
- [x] Template: `app/templates/vc/firm.html`

---

## Phase 2 — Growth (Weeks 9–16)

- [ ] Keyword alerts — email user when new article matches saved keyword
- [ ] Team workspaces — shared collections across multiple users
- [ ] Export to CSV / PDF
- [ ] Trending topics analytics dashboard
- [ ] Paid tier — gate AI summaries behind `user.is_paid` flag (EDGAR refresh already gated)
- [ ] Redis caching for feed queries (mitigate NewsAPI rate limits)
- [ ] More public companies — expand EDGAR seed list beyond current set
- [ ] Historical job-posting chart UI on company detail page

---

## File Map

```
new_proj/
├── run.py                        # Entry point — flask run
├── requirements.txt
├── .env.example
├── app/
│   ├── __init__.py               # App factory + APScheduler (ingest 30 min, EDGAR/jobs 24 h)
│   ├── config.py                 # Env-based config
│   ├── extensions.py             # db, login_manager
│   ├── models/
│   │   └── models.py             # User, Article, Like, Collection, CollectionItem,
│   │                             # PublicCompany, FinancialSnapshot, JobPostingCount, VCFirm
│   ├── routes/
│   │   ├── feed.py               # /, /like, /save, /summarize
│   │   ├── auth.py               # /auth/login, /callback, /logout
│   │   ├── profile.py            # /profile/ — stub
│   │   ├── admin.py              # /admin/ — stub
│   │   ├── public_markets.py     # /public/, /public/<id>, /public/refresh
│   │   └── vc.py                 # /vc/, /vc/<id>, /vc/thesis
│   ├── services/
│   │   ├── ingestion.py          # ingest_rss(), ingest_newsapi() — both call tag_category()
│   │   ├── summarizer.py         # summarize_article() + tag_category() via Claude Haiku
│   │   ├── digest.py             # send_daily_digest() via SendGrid
│   │   ├── edgar.py              # seed_companies(), refresh_all() via SEC EDGAR
│   │   ├── jobs.py               # get_latest_count(), get_mom_change(), refresh_all_jobs()
│   │   ├── thesis.py             # analyze_thesis() — Claude-powered VC matching
│   │   └── vc_data.py            # seed_vc_firms() — 25 firm seed dataset
│   ├── templates/
│   │   ├── base.html
│   │   ├── feed/index.html
│   │   ├── public/index.html     # Public markets table
│   │   ├── public/company.html   # Company financial + job detail
│   │   ├── vc/index.html         # VC firm browser
│   │   ├── vc/firm.html          # Firm profile + AI thesis matcher
│   │   ├── profile/{index,settings,collection}.html
│   │   ├── admin/index.html
│   │   └── email/digest.html
│   └── static/css/main.css
└── tests/
    ├── test_ingestion.py
    └── test_feed.py
```

---

## Required Environment Variables

```
SECRET_KEY=
DATABASE_URL=postgresql://localhost/pulseboard
AUTH0_DOMAIN=
AUTH0_CLIENT_ID=
AUTH0_CLIENT_SECRET=
AUTH0_CALLBACK_URL=http://localhost:5000/auth/callback
NEWS_API_KEY=
ANTHROPIC_API_KEY=
SENDGRID_API_KEY=
MAIL_FROM=digest@pulseboard.io
```

---

## Immediate Next Steps

1. End-to-end test with real Auth0 credentials + live PostgreSQL DB
2. Beta test with real users
