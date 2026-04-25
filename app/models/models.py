from datetime import datetime, timezone
from flask_login import UserMixin
from ..extensions import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    auth0_id = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    avatar_url = db.Column(db.String(512))
    is_paid = db.Column(db.Boolean, default=False)
    keywords = db.Column(db.Text, default="")  # comma-separated
    digest_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    likes = db.relationship("Like", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    collections = db.relationship("Collection", backref="user", lazy="dynamic", cascade="all, delete-orphan")


class Article(db.Model):
    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    url_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    url = db.Column(db.String(1024), nullable=False)
    title = db.Column(db.String(512), nullable=False)
    source = db.Column(db.String(255))
    published_at = db.Column(db.DateTime)
    content_snippet = db.Column(db.Text)
    ai_summary = db.Column(db.Text)
    category = db.Column(db.String(128))
    like_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    likes = db.relationship("Like", backref="article", lazy="dynamic", cascade="all, delete-orphan")


class Like(db.Model):
    __tablename__ = "likes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    value = db.Column(db.SmallInteger, default=1)  # 1 = like, -1 = dislike
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("user_id", "article_id"),)


class Collection(db.Model):
    __tablename__ = "collections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    items = db.relationship("CollectionItem", backref="collection", lazy="dynamic", cascade="all, delete-orphan")


class CollectionItem(db.Model):
    __tablename__ = "collection_items"

    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey("collections.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    saved_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    article = db.relationship("Article")

    __table_args__ = (db.UniqueConstraint("collection_id", "article_id"),)
