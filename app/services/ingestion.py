import hashlib
import feedparser
import requests
from datetime import datetime, timezone
from flask import current_app
from ..models.models import Article
from ..extensions import db
from .summarizer import tag_category

RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://www.theinformation.com/feed",
    "https://sifted.eu/feed",
]


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _parse_date(entry) -> datetime | None:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return None


def ingest_rss():
    added = 0
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            h = _url_hash(url)
            if Article.query.filter_by(url_hash=h).first():
                continue
            article = Article(
                url_hash=h,
                url=url,
                title=entry.get("title", "")[:512],
                source=feed.feed.get("title", feed_url),
                published_at=_parse_date(entry),
                content_snippet=(entry.get("summary", "") or "")[:1000],
            )
            article.category = tag_category(article)
            db.session.add(article)
            added += 1
    db.session.commit()
    return added


def ingest_newsapi(query="startup funding AI"):
    api_key = current_app.config.get("NEWS_API_KEY")
    if not api_key:
        return 0
    resp = requests.get(
        "https://newsapi.org/v2/everything",
        params={"q": query, "language": "en", "sortBy": "publishedAt", "pageSize": 50},
        headers={"X-Api-Key": api_key},
        timeout=10,
    )
    if not resp.ok:
        return 0
    added = 0
    for item in resp.json().get("articles", []):
        url = item.get("url", "")
        if not url:
            continue
        h = _url_hash(url)
        if Article.query.filter_by(url_hash=h).first():
            continue
        published = None
        if item.get("publishedAt"):
            try:
                published = datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00"))
            except ValueError:
                pass
        article = Article(
            url_hash=h,
            url=url,
            title=(item.get("title") or "")[:512],
            source=(item.get("source", {}).get("name") or "")[:255],
            published_at=published,
            content_snippet=(item.get("description") or "")[:1000],
        )
        article.category = tag_category(article)
        db.session.add(article)
        added += 1
    db.session.commit()
    return added
