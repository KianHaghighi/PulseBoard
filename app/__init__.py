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

    init_oauth(app)

    app.register_blueprint(feed_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(profile_bp, url_prefix="/profile")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(public_bp, url_prefix="/public")

    with app.app_context():
        db.create_all()
        from .services.edgar import seed_companies
        seed_companies()

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

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_ingest, "interval", minutes=30, id="ingest")
    scheduler.add_job(run_edgar_refresh, "interval", hours=24, id="edgar_refresh")
    scheduler.start()
