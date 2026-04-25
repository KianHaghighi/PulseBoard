# PulseBoard — Development Plan

> Market Research & Startup Intelligence Platform  
> Based on PRD v0.2 | Updated 2026-04-25

---

## Tech Stack (Decided)

| Layer | Choice |
|---|---|
| Backend | Flask (Python) |
| Frontend | Jinja2 templates (server-side) |
| Database | PostgreSQL + SQLAlchemy |
| Auth | Auth0 (authlib) |
| News ingestion | feedparser (RSS) + NewsAPI |
| AI summarization | Anthropic Claude (Haiku) |
| Email digest | SendGrid |
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
- [x] Populate `requirements.txt` with all deps (added `apscheduler==3.10.4`)

### Week 3–4: Feed UI, Filtering, Search, Like/Dislike

- [x] Feed route with pagination, search, category filter, sort by recent/popular (`app/routes/feed.py`)
- [x] Like/dislike endpoint with toggle logic (`/like/<id>`)
- [x] Save-to-collection endpoint (`/save/<id>`)
- [x] Base template + feed template (`app/templates/`)
- [ ] Article category auto-tagging (category field exists on model, not yet populated by ingestion)
- [ ] Keyword filtering by user's saved keywords (use `current_user.keywords` in feed query)

### Week 5–6: Bookmarking, Collections, AI Summaries

- [x] Collection and CollectionItem models
- [x] Save article to collection endpoint
- [x] AI summarization via Anthropic Claude Haiku (`app/services/summarizer.py`)
- [x] On-demand summarize endpoint (`/summarize/<id>`)
- [x] Profile / collection view templates
- [ ] Profile route: view collections, manage keywords, toggle digest (`app/routes/profile.py` — stub exists)
- [ ] Create / delete collection UI
- [ ] Remove article from collection

### Week 7–8: Email Digest, Admin Panel, Polish, Beta

- [x] Daily digest service with SendGrid (`app/services/digest.py`)
- [x] Digest email template (`app/templates/email/digest.html`)
- [x] Admin blueprint registered
- [ ] Admin route: list users, trigger manual ingest, view article count (`app/routes/admin.py` — stub exists)
- [ ] Scheduler to fire `send_daily_digest()` nightly
- [ ] User settings page: save keywords, toggle digest on/off
- [ ] Mobile-responsive CSS pass
- [ ] `run.py` working end-to-end with a real DB connection
- [ ] Beta test with real Auth0 credentials + live DB

---

## Phase 2 — Growth (Weeks 9–16)

- [ ] Keyword alerts — email user when new article matches saved keyword
- [ ] Team workspaces — shared collections across multiple users
- [ ] Export to CSV / PDF
- [ ] Trending topics analytics dashboard
- [ ] Paid tier — gate AI summaries behind `user.is_paid` flag
- [ ] Redis caching for feed queries (mitigate NewsAPI rate limits)

---

## File Map

```
new_proj/
├── run.py                        # Entry point — flask run
├── requirements.txt
├── .env.example
├── app/
│   ├── __init__.py               # App factory
│   ├── config.py                 # Env-based config
│   ├── extensions.py             # db, login_manager
│   ├── models/
│   │   └── models.py             # User, Article, Like, Collection, CollectionItem
│   ├── routes/
│   │   ├── feed.py               # /, /like, /save, /summarize
│   │   ├── auth.py               # /auth/login, /callback, /logout
│   │   ├── profile.py            # /profile/ — needs implementation
│   │   └── admin.py              # /admin/ — needs implementation
│   ├── services/
│   │   ├── ingestion.py          # ingest_rss(), ingest_newsapi()
│   │   ├── summarizer.py         # summarize_article() via Anthropic
│   │   └── digest.py             # send_daily_digest() via SendGrid
│   ├── templates/
│   │   ├── base.html
│   │   ├── feed/index.html
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

1. Fix `init_oauth()` — call it inside `create_app()` in `app/__init__.py`
2. Implement `app/routes/profile.py` — settings (keywords, digest toggle) + collections view
3. Implement `app/routes/admin.py` — user list + manual ingest trigger
4. Add article category tagging in `ingest_rss()` / `ingest_newsapi()`
5. Add a scheduler (APScheduler) for ingestion and digest
6. End-to-end test with real credentials

---

## Open Questions

- Deployment target: Render/Railway (simpler) vs DigitalOcean VPS (more control)?
- Free tier scope: gate AI summaries behind paid plan, or allow N free/day?
- Add Redis now for caching, or defer to Phase 2?
