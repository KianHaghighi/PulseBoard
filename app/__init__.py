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

    init_oauth(app)

    app.register_blueprint(feed_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(profile_bp, url_prefix="/profile")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(public_bp, url_prefix="/public")
    app.register_blueprint(vc_bp, url_prefix="/vc")

    with app.app_context():
        db.create_all()
        from .services.edgar import seed_companies
        from .services.vc_data import seed_vc_firms
        seed_companies()
        seed_vc_firms()

    if not app.config.get("TESTING"):
        _start_scheduler(app)

    return app


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
    scheduler.add_job(run_digest, "cron", hour=8, minute=0, id="daily_digest")
    scheduler.start()
