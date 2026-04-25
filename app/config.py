import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://localhost/pulseboard")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Auth0
    AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
    AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID")
    AUTH0_CLIENT_SECRET = os.environ.get("AUTH0_CLIENT_SECRET")
    AUTH0_CALLBACK_URL = os.environ.get("AUTH0_CALLBACK_URL", "http://localhost:5000/auth/callback")

    # News ingestion
    NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

    # AI summarization
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

    # Email
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    MAIL_FROM = os.environ.get("MAIL_FROM", "digest@pulseboard.io")
