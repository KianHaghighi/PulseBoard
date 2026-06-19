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
    portfolios = db.relationship("Portfolio", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    valuation_analyses = db.relationship("ValuationAnalysis", backref="user", lazy="dynamic", cascade="all, delete-orphan")


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


class PublicCompany(db.Model):
    __tablename__ = "public_companies"

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    cik = db.Column(db.String(10), unique=True, nullable=False)
    sector = db.Column(db.String(128))
    last_refreshed_at = db.Column(db.DateTime)

    snapshots = db.relationship(
        "FinancialSnapshot", backref="company", lazy="dynamic",
        cascade="all, delete-orphan",
    )
    job_counts = db.relationship(
        "JobPostingCount", backref="public_company", lazy="dynamic",
        foreign_keys="JobPostingCount.public_company_id",
    )


class FinancialSnapshot(db.Model):
    __tablename__ = "financial_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("public_companies.id"), nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    period_type = db.Column(db.String(10), nullable=False)  # "annual" | "quarterly"
    fiscal_year = db.Column(db.Integer)
    fiscal_period = db.Column(db.String(10))  # FY, Q1, Q2, Q3, Q4
    revenue = db.Column(db.BigInteger)
    net_income = db.Column(db.BigInteger)
    eps_basic = db.Column(db.Float)
    total_assets = db.Column(db.BigInteger)
    cash = db.Column(db.BigInteger)

    __table_args__ = (db.UniqueConstraint("company_id", "period_end", "period_type"),)


class JobPostingCount(db.Model):
    __tablename__ = "job_posting_counts"

    id                = db.Column(db.Integer, primary_key=True)
    company_name      = db.Column(db.String(255), nullable=False, index=True)
    public_company_id = db.Column(db.Integer, db.ForeignKey("public_companies.id"), nullable=True)
    snapshot_date     = db.Column(db.Date, nullable=False)
    posting_count     = db.Column(db.Integer, nullable=False)
    ats_type          = db.Column(db.String(20), nullable=False)
    ats_slug          = db.Column(db.String(128), nullable=False)

    __table_args__ = (db.UniqueConstraint("company_name", "snapshot_date"),)


class Portfolio(db.Model):
    __tablename__ = "portfolios"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    refreshed_at = db.Column(db.DateTime)

    holdings = db.relationship(
        "PortfolioHolding", backref="portfolio", lazy="dynamic", cascade="all, delete-orphan"
    )


class PortfolioHolding(db.Model):
    __tablename__ = "portfolio_holdings"

    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey("portfolios.id"), nullable=False)
    company_name = db.Column(db.String(255), nullable=False)
    ticker = db.Column(db.String(20))           # null = private company
    sector = db.Column(db.String(128))
    investment_type = db.Column(db.String(64))  # Equity, SAFE, Convertible Note, etc.
    shares = db.Column(db.Float)
    cost_per_share = db.Column(db.Float)
    investment_date = db.Column(db.Date)
    private_valuation_usd = db.Column(db.BigInteger)  # total company valuation for private cos
    notes = db.Column(db.Text)
    # Cached market data
    last_price = db.Column(db.Float)
    market_cap = db.Column(db.BigInteger)
    price_refreshed_at = db.Column(db.DateTime)


class ValuationAnalysis(db.Model):
    __tablename__ = "valuation_analyses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    company_name = db.Column(db.String(255), nullable=False)
    ticker = db.Column(db.String(20))
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    data_json = db.Column(db.Text, nullable=False)  # full parsed model as JSON
    current_price = db.Column(db.Float)
    market_cap = db.Column(db.BigInteger)
    price_refreshed_at = db.Column(db.DateTime)


class VCFirm(db.Model):
    __tablename__ = "vc_firms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text)
    website = db.Column(db.String(512))
    hq_city = db.Column(db.String(128))
    founded_year = db.Column(db.Integer)
    focus_sectors = db.Column(db.Text)    # comma-separated
    stages = db.Column(db.Text)           # comma-separated
    check_min_k = db.Column(db.Integer)   # in $K
    check_max_k = db.Column(db.Integer)   # in $K
    aum_usd_bn = db.Column(db.Float)
    notable_portfolio = db.Column(db.Text)  # comma-separated

    @property
    def stage_list(self):
        return [s.strip() for s in (self.stages or "").split(",") if s.strip()]

    @property
    def sector_list(self):
        return [s.strip() for s in (self.focus_sectors or "").split(",") if s.strip()]

    @property
    def portfolio_list(self):
        return [s.strip() for s in (self.notable_portfolio or "").split(",") if s.strip()]
