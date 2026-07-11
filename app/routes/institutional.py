from flask import Blueprint, render_template, request, abort, redirect, url_for
from flask_login import current_user
from ..extensions import db
from ..models.models import InstitutionalManager, InstitutionalHolding

institutional_bp = Blueprint("institutional", __name__)


@institutional_bp.app_template_filter("fmt_holding_money")
def fmt_holding_money(val):
    if val is None:
        return "—"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:.1f}M"
    return f"{sign}${abs_val:,.0f}"


@institutional_bp.app_template_filter("fmt_holding_pct")
def fmt_holding_pct(val):
    if val is None:
        return "—"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.1f}%"


@institutional_bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    managers = InstitutionalManager.query.order_by(InstitutionalManager.name).all()
    if q:
        managers = [m for m in managers if q.lower() in m.name.lower()]

    summaries = []
    for m in managers:
        latest_period = (
            db.session.query(db.func.max(InstitutionalHolding.period_end))
            .filter_by(manager_id=m.id, put_call=None)
            .scalar()
        )
        total_value = None
        if latest_period:
            total_value = (
                db.session.query(db.func.sum(InstitutionalHolding.value_usd))
                .filter_by(manager_id=m.id, period_end=latest_period, put_call=None)
                .scalar()
            )
        summaries.append({"manager": m, "latest_period": latest_period, "total_value": total_value})

    return render_template("institutional/index.html", summaries=summaries, q=q)


@institutional_bp.route("/<int:manager_id>")
def manager(manager_id):
    from ..services.institutional import get_qoq_change

    m = InstitutionalManager.query.get_or_404(manager_id)
    latest_period = (
        db.session.query(db.func.max(InstitutionalHolding.period_end))
        .filter_by(manager_id=m.id, put_call=None)
        .scalar()
    )

    HOLDING_DISPLAY_LIMIT = 50
    rows = []
    total_holdings = 0
    if latest_period:
        total_holdings = (
            InstitutionalHolding.query
            .filter_by(manager_id=m.id, period_end=latest_period, put_call=None)
            .count()
        )
        holdings = (
            InstitutionalHolding.query
            .filter_by(manager_id=m.id, period_end=latest_period, put_call=None)
            .order_by(InstitutionalHolding.value_usd.desc())
            .limit(HOLDING_DISPLAY_LIMIT)
            .all()
        )
        for h in holdings:
            rows.append({"holding": h, "qoq": get_qoq_change(m.id, h.cusip)})

    return render_template(
        "institutional/manager.html", manager=m, rows=rows,
        latest_period=latest_period, total_holdings=total_holdings,
    )


@institutional_bp.route("/refresh", methods=["POST"])
def refresh():
    if not current_user.is_authenticated or not current_user.is_paid:
        abort(403)
    from ..services.institutional import refresh_all
    refresh_all()
    return redirect(url_for("institutional.index"))
