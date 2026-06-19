from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from ..models.models import Article, Like, CollectionItem, Collection
from ..extensions import db

feed_bp = Blueprint("feed", __name__)


@feed_bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    source = request.args.get("source", "").strip()
    sort = request.args.get("sort", "recent")

    all_sources = (
        db.session.query(Article.source)
        .filter(Article.source.isnot(None), Article.source != "")
        .distinct()
        .order_by(Article.source)
        .all()
    )
    all_sources = [row[0] for row in all_sources]

    articles_q = Article.query

    if query:
        articles_q = articles_q.filter(
            Article.title.ilike(f"%{query}%") | Article.content_snippet.ilike(f"%{query}%")
        )
    if category:
        articles_q = articles_q.filter(Article.category == category)
    if source:
        articles_q = articles_q.filter(Article.source == source)

    user_keywords = []
    if current_user.is_authenticated:
        user_keywords = [k.strip() for k in (current_user.keywords or "").split(",") if k.strip()]

    if sort == "for_you":
        if user_keywords:
            kw_filters = []
            for kw in user_keywords:
                kw_filters.append(Article.title.ilike(f"%{kw}%"))
                kw_filters.append(Article.content_snippet.ilike(f"%{kw}%"))
            articles_q = articles_q.filter(or_(*kw_filters))
        articles_q = articles_q.order_by(Article.published_at.desc())
    elif sort == "popular":
        articles_q = articles_q.order_by(Article.like_count.desc())
    else:
        articles_q = articles_q.order_by(Article.published_at.desc())

    articles = articles_q.paginate(page=page, per_page=20, error_out=False)

    user_likes = {}
    collections = []
    if current_user.is_authenticated:
        liked = Like.query.filter_by(user_id=current_user.id).all()
        user_likes = {l.article_id: l.value for l in liked}
        collections = Collection.query.filter_by(user_id=current_user.id).all()

    return render_template(
        "feed/index.html",
        articles=articles,
        user_likes=user_likes,
        collections=collections,
        query=query,
        category=category,
        source=source,
        sort=sort,
        user_keywords=user_keywords,
        all_sources=all_sources,
    )


@feed_bp.route("/like/<int:article_id>", methods=["POST"])
@login_required
def like(article_id):
    value = request.json.get("value", 1)
    article = Article.query.get_or_404(article_id)
    existing = Like.query.filter_by(user_id=current_user.id, article_id=article_id).first()

    if existing:
        if existing.value == value:
            article.like_count -= existing.value
            db.session.delete(existing)
        else:
            article.like_count += value - existing.value
            existing.value = value
    else:
        db.session.add(Like(user_id=current_user.id, article_id=article_id, value=value))
        article.like_count += value

    db.session.commit()
    return jsonify(like_count=article.like_count)


@feed_bp.route("/summarize/<int:article_id>", methods=["POST"])
@login_required
def summarize(article_id):
    from ..services.summarizer import summarize_article
    article = Article.query.get_or_404(article_id)
    summary = summarize_article(article)
    return jsonify(summary=summary)


@feed_bp.route("/save/<int:article_id>", methods=["POST"])
@login_required
def save(article_id):
    collection_id = request.json.get("collection_id")
    Article.query.get_or_404(article_id)
    collection = Collection.query.filter_by(id=collection_id, user_id=current_user.id).first_or_404()

    existing = CollectionItem.query.filter_by(collection_id=collection_id, article_id=article_id).first()
    if not existing:
        db.session.add(CollectionItem(collection_id=collection_id, article_id=article_id))
        db.session.commit()

    return jsonify(saved=True)
