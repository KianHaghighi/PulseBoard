from flask import Flask
from .extensions import db, login_manager
from .config import Config


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)

    db.init_app(app)
    login_manager.init_app(app)

    from .routes.feed import feed_bp
    from .routes.auth import auth_bp, init_oauth
    from .routes.profile import profile_bp
    from .routes.admin import admin_bp

    init_oauth(app)

    app.register_blueprint(feed_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(profile_bp, url_prefix="/profile")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    with app.app_context():
        db.create_all()

    _start_scheduler(app)

    return app


def _start_scheduler(app):
    from apscheduler.schedulers.background import BackgroundScheduler
    from .services.ingestion import ingest_rss, ingest_newsapi

    def run_ingest():
        with app.app_context():
            ingest_rss()
            ingest_newsapi()

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_ingest, "interval", minutes=30, id="ingest")
    scheduler.start()
