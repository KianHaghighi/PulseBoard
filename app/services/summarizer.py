import anthropic
from flask import current_app
from ..models.models import Article
from ..extensions import db

CATEGORIES = ["AI & ML", "Funding", "Startups", "Enterprise", "Crypto & Web3", "Policy", "Science", "Other"]


def tag_category(article: Article) -> str:
    client = anthropic.Anthropic(api_key=current_app.config["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": (
                f"Classify this article into exactly one of these categories: {', '.join(CATEGORIES)}.\n"
                f"Reply with only the category name, nothing else.\n\n"
                f"Title: {article.title}\n"
                f"{article.content_snippet or ''}"
            ),
        }],
    )
    category = message.content[0].text.strip()
    return category if category in CATEGORIES else "Other"


def summarize_article(article: Article) -> str:
    if article.ai_summary:
        return article.ai_summary

    client = anthropic.Anthropic(api_key=current_app.config["ANTHROPIC_API_KEY"])
    prompt = (
        f"Summarize this article in 2-3 sentences for a tech professional. "
        f"Focus on the key insight or event.\n\n"
        f"Title: {article.title}\n\n"
        f"{article.content_snippet or ''}"
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )

    summary = message.content[0].text
    article.ai_summary = summary
    db.session.commit()
    return summary
