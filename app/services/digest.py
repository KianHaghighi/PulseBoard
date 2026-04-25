import sendgrid
from sendgrid.helpers.mail import Mail
from flask import current_app, render_template
from ..models.models import User, Article


def send_daily_digest():
    users = User.query.filter_by(digest_enabled=True).all()
    sent = 0
    for user in users:
        keywords = [k.strip() for k in user.keywords.split(",") if k.strip()]
        articles = _top_articles_for(keywords)
        if not articles:
            continue
        _send_digest_email(user, articles)
        sent += 1
    return sent


def _top_articles_for(keywords: list[str], limit: int = 10):
    from datetime import datetime, timedelta, timezone

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    q = Article.query.filter(Article.published_at >= since)

    if keywords:
        from sqlalchemy import or_
        q = q.filter(
            or_(*[Article.title.ilike(f"%{kw}%") for kw in keywords])
        )

    return q.order_by(Article.like_count.desc()).limit(limit).all()


def _send_digest_email(user: User, articles: list[Article]):
    sg = sendgrid.SendGridAPIClient(api_key=current_app.config["SENDGRID_API_KEY"])
    html = render_template("email/digest.html", user=user, articles=articles)
    message = Mail(
        from_email=current_app.config["MAIL_FROM"],
        to_emails=user.email,
        subject="Your PulseBoard Daily Digest",
        html_content=html,
    )
    sg.send(message)
