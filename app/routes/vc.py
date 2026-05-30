from flask import Blueprint, render_template, request, abort, jsonify
from ..models.models import VCFirm, Article

vc_bp = Blueprint("vc", __name__)

ALL_STAGES = ["Pre-seed", "Seed", "Series A", "Series B", "Series C", "Growth"]


@vc_bp.app_template_filter("fmt_check_k")
def fmt_check_k(val_k):
    if val_k is None:
        return "—"
    if val_k >= 1000:
        return f"${val_k // 1000}M"
    return f"${val_k}K"


@vc_bp.route("/")
def index():
    stage = request.args.get("stage", "").strip()
    q = request.args.get("q", "").strip()

    firms = VCFirm.query.order_by(VCFirm.name).all()

    if stage:
        firms = [f for f in firms if stage in f.stage_list]
    if q:
        firms = [f for f in firms if q.lower() in (f.focus_sectors or "").lower()
                 or q.lower() in (f.name or "").lower()]

    return render_template(
        "vc/index.html",
        firms=firms,
        all_stages=ALL_STAGES,
        stage_filter=stage,
        q=q,
    )


@vc_bp.route("/<int:firm_id>")
def firm(firm_id):
    from ..services.jobs import get_latest_count
    f = VCFirm.query.get_or_404(firm_id)
    portfolio_jobs = {}
    for co_name in f.portfolio_list:
        snap = get_latest_count(co_name)
        if snap:
            portfolio_jobs[co_name] = snap.posting_count
    return render_template("vc/firm.html", firm=f, portfolio_jobs=portfolio_jobs)


@vc_bp.route("/thesis", methods=["POST"])
def thesis():
    from ..services.thesis import analyze_thesis

    body = request.get_json(silent=True) or {}
    thesis_text = body.get("thesis", "").strip()
    if len(thesis_text) < 20:
        return jsonify({"error": "Please write at least a sentence describing your startup."}), 400

    try:
        result = analyze_thesis(thesis_text)
    except Exception as exc:
        return jsonify({"error": f"Analysis failed: {exc}"}), 500

    # Enrich article matches with live DB data
    article_ids = [m["id"] for m in result.get("article_matches", [])]
    art_map = {}
    if article_ids:
        art_map = {a.id: a for a in Article.query.filter(Article.id.in_(article_ids)).all()}

    enriched_articles = []
    for m in result.get("article_matches", []):
        art = art_map.get(m["id"])
        if art:
            enriched_articles.append({
                "id": art.id,
                "title": art.title,
                "url": art.url,
                "source": art.source,
                "category": art.category,
                "reason": m["reason"],
            })

    # Enrich VC matches
    vc_ids = [m["id"] for m in result.get("vc_matches", [])]
    firm_map = {}
    if vc_ids:
        firm_map = {f.id: f for f in VCFirm.query.filter(VCFirm.id.in_(vc_ids)).all()}

    enriched_vcs = []
    for m in result.get("vc_matches", []):
        f = firm_map.get(m["id"])
        if f:
            enriched_vcs.append({
                "id": f.id,
                "name": f.name,
                "website": f.website,
                "stages": f.stage_list,
                "hq_city": f.hq_city,
                "reason": m["reason"],
            })

    return jsonify({
        "thesis_feedback": result.get("thesis_feedback", ""),
        "vc_matches": enriched_vcs,
        "article_matches": enriched_articles,
    })
