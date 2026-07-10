import io
import json
from datetime import datetime, timezone

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, flash, abort, send_file,
)
from flask_login import login_required, current_user

from ..extensions import db
from ..models.models import Portfolio, PortfolioHolding, ValuationAnalysis
from ..services.portfolio_analyzer import (
    parse_excel, fetch_market_data,
    build_holding_analysis, build_portfolio_summary,
    parse_valuation_model, DEMO_USER_AUTH0_ID, DEMO_COMPANY_NAME,
)

portfolio_bp = Blueprint("portfolio", __name__)


@portfolio_bp.app_template_filter("fmt_price")
def fmt_price(val):
    """Format a float dollar value with cents (per-share prices, small amounts)."""
    if val is None:
        return "—"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{sign}${abs_val:,.0f}"
    return f"{sign}${abs_val:,.2f}"


@portfolio_bp.app_template_filter("fmt_pnl")
def fmt_pnl(val):
    """Format P&L with explicit + / - sign."""
    if val is None:
        return "—"
    abs_val = abs(val)
    sign = "+" if val >= 0 else "-"
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{sign}${abs_val:,.0f}"
    return f"{sign}${abs_val:,.2f}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@portfolio_bp.route("/")
def index():
    portfolios, analyses = [], []
    if current_user.is_authenticated:
        portfolios = (
            Portfolio.query
            .filter_by(user_id=current_user.id)
            .order_by(Portfolio.created_at.desc())
            .all()
        )
        analyses = (
            ValuationAnalysis.query
            .filter_by(user_id=current_user.id)
            .order_by(ValuationAnalysis.uploaded_at.desc())
            .all()
        )
    return render_template("portfolio/index.html", portfolios=portfolios, analyses=analyses)


@portfolio_bp.route("/template")
@login_required
def download_template():
    """Serve a sample Excel template so users know the expected column format."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Portfolio"
    ws.append([
        "Company Name", "Ticker", "Sector", "Investment Type",
        "Shares", "Cost Per Share", "Investment Date",
        "Private Valuation ($)", "Notes",
    ])
    ws.append(["Apple Inc.", "AAPL", "Technology", "Equity", 50, 150.00, "2023-01-15", "", "Public stock"])
    ws.append(["Startup XYZ", "", "Healthcare", "SAFE", 100000, 0.01, "2022-06-01", 5000000, "Pre-seed SAFE"])
    ws.append(["Series A Co.", "", "Fintech", "Equity", 200000, 0.50, "2023-03-10", 20000000, "Series A"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name="portfolio_template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@portfolio_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    f = request.files.get("excel_file")
    name = request.form.get("portfolio_name", "").strip()

    if not f or not f.filename:
        flash("Please select a file.", "error")
        return redirect(url_for("portfolio.index"))
    if not f.filename.lower().endswith(".xlsx"):
        flash("Only .xlsx files are supported.", "error")
        return redirect(url_for("portfolio.index"))

    file_bytes = f.read()
    holdings_data, errors = parse_excel(file_bytes)

    if not holdings_data:
        msg = "No valid holdings found. " + (errors[0] if errors else "Check that your file has the correct column headers.")
        flash(msg, "error")
        return redirect(url_for("portfolio.index"))

    if not name:
        name = f.filename.rsplit(".", 1)[0]

    portfolio = Portfolio(user_id=current_user.id, name=name)
    db.session.add(portfolio)
    db.session.flush()  # populate portfolio.id

    for h_data in holdings_data:
        holding = PortfolioHolding(portfolio_id=portfolio.id, **h_data)
        db.session.add(holding)
        if holding.ticker:
            mdata = fetch_market_data(holding.ticker)
            if mdata:
                holding.last_price = mdata.get("last_price")
                holding.market_cap = mdata.get("market_cap")
                holding.price_refreshed_at = datetime.now(timezone.utc)

    portfolio.refreshed_at = datetime.now(timezone.utc)
    db.session.commit()

    suffix = f" ({len(errors)} row(s) skipped due to errors)" if errors else ""
    flash(f"Imported {len(holdings_data)} holding(s){suffix}.", "success")
    return redirect(url_for("portfolio.view", portfolio_id=portfolio.id))


@portfolio_bp.route("/<int:portfolio_id>")
@login_required
def view(portfolio_id):
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    if portfolio.user_id != current_user.id:
        abort(403)

    holdings = (
        portfolio.holdings
        .order_by(PortfolioHolding.company_name)
        .all()
    )
    analyses = [build_holding_analysis(h) for h in holdings]
    summary = build_portfolio_summary(analyses)

    from ..models.models import PublicCompany, FinancialSnapshot
    edgar_data: dict = {}
    for a in analyses:
        ticker = a["holding"].ticker
        if ticker:
            company = PublicCompany.query.filter_by(ticker=ticker).first()
            if company:
                snap = (
                    FinancialSnapshot.query
                    .filter_by(company_id=company.id, period_type="annual")
                    .order_by(FinancialSnapshot.period_end.desc())
                    .first()
                )
                edgar_data[ticker] = snap

    return render_template(
        "portfolio/view.html",
        portfolio=portfolio,
        analyses=analyses,
        summary=summary,
        edgar_data=edgar_data,
    )


@portfolio_bp.route("/<int:portfolio_id>/refresh", methods=["POST"])
@login_required
def refresh(portfolio_id):
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    if portfolio.user_id != current_user.id:
        abort(403)

    refreshed = 0
    for holding in portfolio.holdings.all():
        if holding.ticker:
            mdata = fetch_market_data(holding.ticker)
            if mdata:
                holding.last_price = mdata.get("last_price")
                holding.market_cap = mdata.get("market_cap")
                holding.price_refreshed_at = datetime.now(timezone.utc)
                refreshed += 1

    portfolio.refreshed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash(f"Refreshed market data for {refreshed} public holding(s).", "success")
    return redirect(url_for("portfolio.view", portfolio_id=portfolio_id))


@portfolio_bp.route("/<int:portfolio_id>/delete", methods=["POST"])
@login_required
def delete(portfolio_id):
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    if portfolio.user_id != current_user.id:
        abort(403)
    db.session.delete(portfolio)
    db.session.commit()
    flash("Portfolio deleted.", "success")
    return redirect(url_for("portfolio.index"))


# ---------------------------------------------------------------------------
# Valuation Model Analysis
# ---------------------------------------------------------------------------

@portfolio_bp.route("/analyze/upload", methods=["POST"])
@login_required
def upload_analysis():
    f = request.files.get("model_file")
    company_name = request.form.get("company_name", "").strip()
    ticker = request.form.get("ticker", "").strip().upper()

    if not f or not f.filename:
        flash("Please select a file.", "error")
        return redirect(url_for("portfolio.index"))
    if not f.filename.lower().endswith(".xlsx"):
        flash("Only .xlsx files are supported.", "error")
        return redirect(url_for("portfolio.index"))
    if not company_name:
        flash("Please enter a company name.", "error")
        return redirect(url_for("portfolio.index"))

    file_bytes = f.read()
    model_data = parse_valuation_model(file_bytes)

    if not model_data:
        flash("Could not recognize the valuation model format. Make sure your Excel has 'IS Summary' or 'DCF' sheets.", "error")
        return redirect(url_for("portfolio.index"))

    analysis = ValuationAnalysis(
        user_id=current_user.id,
        company_name=company_name,
        ticker=ticker or None,
        data_json=json.dumps(model_data),
    )
    db.session.add(analysis)
    db.session.flush()

    if ticker:
        mdata = fetch_market_data(ticker)
        if mdata:
            analysis.current_price = mdata.get("last_price")
            analysis.market_cap = mdata.get("market_cap")
            analysis.price_refreshed_at = datetime.now(timezone.utc)

    db.session.commit()
    flash(f"Valuation model for {company_name} imported successfully.", "success")
    return redirect(url_for("portfolio.view_analysis", analysis_id=analysis.id))


@portfolio_bp.route("/analyze/demo")
def view_demo_analysis():
    """Public sample valuation model — no account required."""
    from ..models.models import User
    demo_user = User.query.filter_by(auth0_id=DEMO_USER_AUTH0_ID).first()
    analysis = ValuationAnalysis.query.filter_by(
        user_id=demo_user.id, company_name=DEMO_COMPANY_NAME,
    ).first_or_404()

    model_data = json.loads(analysis.data_json)

    return render_template(
        "portfolio/analysis_view.html",
        analysis=analysis,
        model=model_data,
        edgar_snap=None,
        is_demo=True,
    )


@portfolio_bp.route("/analyze/<int:analysis_id>")
@login_required
def view_analysis(analysis_id):
    analysis = ValuationAnalysis.query.get_or_404(analysis_id)
    if analysis.user_id != current_user.id:
        abort(403)

    model_data = json.loads(analysis.data_json)

    from ..models.models import PublicCompany, FinancialSnapshot
    edgar_snap = None
    if analysis.ticker:
        company = PublicCompany.query.filter_by(ticker=analysis.ticker).first()
        if company:
            edgar_snap = (
                FinancialSnapshot.query
                .filter_by(company_id=company.id, period_type="annual")
                .order_by(FinancialSnapshot.period_end.desc())
                .first()
            )

    return render_template(
        "portfolio/analysis_view.html",
        analysis=analysis,
        model=model_data,
        edgar_snap=edgar_snap,
    )


@portfolio_bp.route("/analyze/<int:analysis_id>/refresh", methods=["POST"])
@login_required
def refresh_analysis(analysis_id):
    analysis = ValuationAnalysis.query.get_or_404(analysis_id)
    if analysis.user_id != current_user.id:
        abort(403)
    if analysis.ticker:
        mdata = fetch_market_data(analysis.ticker)
        if mdata:
            analysis.current_price = mdata.get("last_price")
            analysis.market_cap = mdata.get("market_cap")
            analysis.price_refreshed_at = datetime.now(timezone.utc)
            db.session.commit()
            flash("Live price updated.", "success")
        else:
            flash("Could not fetch live price for this ticker.", "error")
    else:
        flash("No ticker set — cannot fetch live price.", "error")
    return redirect(url_for("portfolio.view_analysis", analysis_id=analysis_id))


@portfolio_bp.route("/analyze/<int:analysis_id>/delete", methods=["POST"])
@login_required
def delete_analysis(analysis_id):
    analysis = ValuationAnalysis.query.get_or_404(analysis_id)
    if analysis.user_id != current_user.id:
        abort(403)
    db.session.delete(analysis)
    db.session.commit()
    flash("Analysis deleted.", "success")
    return redirect(url_for("portfolio.index"))
