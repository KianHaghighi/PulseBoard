from flask import Blueprint, render_template, redirect, url_for, request, abort
from flask_login import login_required, current_user
from ..models.models import Article, User
from ..extensions import db

admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_paid:
            abort(403)
        return f(*args, **kwargs)

    return decorated


@admin_bp.route("/")
@login_required
@admin_required
def index():
    user_count = User.query.count()
    article_count = Article.query.count()
    recent_articles = Article.query.order_by(Article.created_at.desc()).limit(20).all()
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template(
        "admin/index.html",
        user_count=user_count,
        article_count=article_count,
        recent_articles=recent_articles,
        users=users,
    )


@admin_bp.route("/ingest", methods=["POST"])
@login_required
@admin_required
def trigger_ingest():
    from ..services.ingestion import ingest_rss, ingest_newsapi
    from flask import flash
    ingest_rss()
    ingest_newsapi()
    flash("Ingestion triggered successfully.", "success")
    return redirect(url_for("admin.index"))


@admin_bp.route("/institutional/refresh", methods=["POST"])
@login_required
@admin_required
def trigger_institutional_refresh():
    from ..services.institutional import refresh_all
    from flask import flash
    refresh_all()
    flash("Institutional ownership refresh triggered successfully.", "success")
    return redirect(url_for("admin.index"))


@admin_bp.route("/articles/<int:article_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_article(article_id):
    article = Article.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    return redirect(url_for("admin.index"))
