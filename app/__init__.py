from datetime import datetime, timezone
from flask import Flask
from flask_session import Session
from .extensions import db, login_manager
from .config import Config


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)

    # Initialize session
    Session(app)

    db.init_app(app)
    login_manager.init_app(app)

    from .routes.feed import feed_bp
    from .routes.auth import auth_bp, init_oauth
    from .routes.profile import profile_bp
    from .routes.admin import admin_bp
    from .routes.public_markets import public_bp
    from .routes.vc import vc_bp
    from .routes.portfolio import portfolio_bp
    from .routes.institutional import institutional_bp

    init_oauth(app)

    app.register_blueprint(feed_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(profile_bp, url_prefix="/profile")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(public_bp, url_prefix="/public")
    app.register_blueprint(vc_bp, url_prefix="/vc")
    app.register_blueprint(portfolio_bp, url_prefix="/portfolio")
    app.register_blueprint(institutional_bp, url_prefix="/institutional")

    with app.app_context():
        db.create_all()
        _patch_public_companies_cusip_column()
        _patch_source_citation_columns()
        from .services.edgar import seed_companies
        from .services.vc_data import seed_vc_firms
        from .services.portfolio_analyzer import seed_demo_valuation
        from .services.institutional import seed_managers
        seed_companies()
        seed_vc_firms()
        seed_demo_valuation()
        seed_managers()

    if not app.config.get("TESTING"):
        _start_scheduler(app)

    return app


def _add_column_if_missing(conn, table: str, column: str, coltype: str):
    """db.create_all() only creates missing tables, it never alters existing
    ones, and this project has no migration tool — deployments that predate a
    newly-added column need it patched in by hand, idempotently, on boot."""
    from sqlalchemy import text

    if db.engine.dialect.name == "sqlite":
        cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]
        if column in cols:
            return
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))
    else:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}"))


def _patch_public_companies_cusip_column():
    from sqlalchemy import text

    with db.engine.begin() as conn:
        _add_column_if_missing(conn, "public_companies", "cusip", "VARCHAR(9)")
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_public_companies_cusip "
            "ON public_companies (cusip)"
        ))


def _patch_source_citation_columns():
    """Per-row audit trail: which exact SEC filing a financial snapshot or
    institutional holding was sourced from."""
    with db.engine.begin() as conn:
        _add_column_if_missing(conn, "financial_snapshots", "source_accn", "VARCHAR(20)")
        _add_column_if_missing(conn, "institutional_holdings", "accession_number", "VARCHAR(20)")


def _start_scheduler(app):
    from apscheduler.schedulers.background import BackgroundScheduler
    from .services.ingestion import ingest_rss, ingest_newsapi

    def run_ingest():
        with app.app_context():
            ingest_rss()
            ingest_newsapi()

    def run_edgar_refresh():
        with app.app_context():
            from .services.edgar import refresh_all
            refresh_all()

    def run_jobs_refresh():
        with app.app_context():
            from .services.jobs import refresh_all_jobs
            refresh_all_jobs()

    def run_institutional_refresh():
        with app.app_context():
            from .services.institutional import refresh_all
            refresh_all()

    def run_digest():
        with app.app_context():
            from .services.digest import send_daily_digest
            send_daily_digest()

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_ingest, "interval", minutes=30, id="ingest")
    scheduler.add_job(
        run_edgar_refresh, "interval", hours=24, id="edgar_refresh",
        next_run_time=datetime.now(timezone.utc),
    )
    scheduler.add_job(
        run_jobs_refresh, "interval", hours=24, id="jobs_refresh",
        next_run_time=datetime.now(timezone.utc),
    )
    # Deliberately not run immediately at boot like the other refresh jobs: a full
    # refresh does per-row upserts against the DB for ~22k holdings across all
    # managers (Citadel alone reports 12.8k positions), which is heavy enough on a
    # free-tier instance + remote Postgres to starve the process during the startup
    # window. First run is deferred to the normal 24h interval; trigger manually via
    # the admin panel when you want it sooner.
    scheduler.add_job(
        run_institutional_refresh, "interval", hours=24, id="institutional_refresh",
    )
    scheduler.add_job(run_digest, "cron", hour=8, minute=0, id="daily_digest")
    scheduler.start()
