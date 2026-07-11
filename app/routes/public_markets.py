from flask import Blueprint, render_template, redirect, url_for, abort, jsonify
from flask_login import current_user
from ..models.models import PublicCompany, FinancialSnapshot, JobPostingCount
from ..services.jobs import get_latest_count, get_mom_change

public_bp = Blueprint("public", __name__)


@public_bp.app_template_filter("fmt_money")
def fmt_money(val):
    if val is None:
        return "—"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1_000_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000_000:.2f}T"
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000:.1f}B"
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:.0f}M"
    return f"{sign}${abs_val:,}"


@public_bp.app_template_filter("fmt_eps")
def fmt_eps(val):
    if val is None:
        return "—"
    return f"${val:.2f}"


@public_bp.app_template_filter("fmt_pct")
def fmt_pct(val):
    if val is None:
        return "—"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.1f}%"


@public_bp.app_template_filter("sec_filing_url")
def sec_filing_url(cik, accession_number):
    """Deep link to the exact SEC EDGAR filing index page a data point came from."""
    if not cik or not accession_number:
        return None
    cik_nolead = str(int(cik))
    accn_nodash = accession_number.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_nolead}/{accn_nodash}/{accession_number}-index.htm"


@public_bp.route("/")
def index():
    companies = PublicCompany.query.order_by(PublicCompany.ticker).all()
    summaries = []
    for c in companies:
        latest = (FinancialSnapshot.query
                  .filter_by(company_id=c.id, period_type="annual")
                  .order_by(FinancialSnapshot.period_end.desc())
                  .first())
        prev = (FinancialSnapshot.query
                .filter_by(company_id=c.id, period_type="annual")
                .order_by(FinancialSnapshot.period_end.desc())
                .offset(1).first())
        yoy = None
        if latest and prev and prev.revenue:
            yoy = (latest.revenue - prev.revenue) / prev.revenue * 100
        job_snap = get_latest_count(c.name)
        summaries.append({
            "company": c,
            "latest": latest,
            "yoy": yoy,
            "job_snap": job_snap,
            "job_mom": get_mom_change(c.name) if job_snap else None,
        })
    return render_template("public/index.html", summaries=summaries)


@public_bp.route("/<int:company_id>")
def company(company_id):
    c = PublicCompany.query.get_or_404(company_id)
    annual = (FinancialSnapshot.query
              .filter_by(company_id=c.id, period_type="annual")
              .order_by(FinancialSnapshot.period_end.desc())
              .limit(4).all())
    quarterly = (FinancialSnapshot.query
                 .filter_by(company_id=c.id, period_type="quarterly")
                 .order_by(FinancialSnapshot.period_end.desc())
                 .limit(8).all())
    job_history = (JobPostingCount.query
                   .filter_by(company_name=c.name)
                   .order_by(JobPostingCount.snapshot_date.desc())
                   .limit(30).all())
    job_latest = job_history[0] if job_history else None
    job_mom = get_mom_change(c.name) if job_latest else None

    holders = []
    if c.cusip:
        from ..services.institutional import get_holders_for_company
        holders = get_holders_for_company(c.id)

    return render_template(
        "public/company.html",
        company=c, annual=annual, quarterly=quarterly,
        job_history=job_history, job_latest=job_latest, job_mom=job_mom,
        holders=holders,
    )


@public_bp.route("/refresh", methods=["POST"])
def refresh():
    if not current_user.is_authenticated or not current_user.is_paid:
        abort(403)
    from ..services.edgar import refresh_all
    refresh_all()
    return redirect(url_for("public.index"))
