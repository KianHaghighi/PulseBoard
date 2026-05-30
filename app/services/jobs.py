import time
import requests
from datetime import date, timedelta
from ..extensions import db

GREENHOUSE_BASE = "https://boards-api.greenhouse.io/v1/boards"
LEVER_BASE = "https://api.lever.co/v0/postings"

# (ats_type, ats_slug) keyed by the canonical company name that appears in
# PublicCompany.name or VCFirm.notable_portfolio CSV fields.
ATS_MAPPING: dict[str, tuple[str, str]] = {
    # ── Public companies (only those confirmed on free ATS) ──────────────────
    "Tesla Inc.":            ("lever",      "tesla"),
    "Palantir Technologies": ("greenhouse", "palantir"),
    "Snowflake Inc.":        ("greenhouse", "snowflake"),

    # ── VC portfolio companies ───────────────────────────────────────────────
    # Greenhouse
    "Airbnb":       ("greenhouse", "airbnb"),
    "Stripe":       ("greenhouse", "stripe"),
    "Dropbox":      ("greenhouse", "dropbox"),
    "Coinbase":     ("greenhouse", "coinbase"),
    "DoorDash":     ("greenhouse", "doordash"),
    "Reddit":       ("greenhouse", "reddit"),
    "Okta":         ("greenhouse", "okta"),
    "Figma":        ("greenhouse", "figma"),
    "Roblox":       ("greenhouse", "roblox"),
    "Discord":      ("greenhouse", "discord"),
    "HubSpot":      ("greenhouse", "hubspot"),
    "Canva":        ("greenhouse", "canva"),
    "Shopify":      ("greenhouse", "shopify"),
    "Twilio":       ("greenhouse", "twilio"),
    "Duolingo":     ("greenhouse", "duolingo"),
    "Cloudflare":   ("greenhouse", "cloudflare"),
    "Databricks":   ("greenhouse", "databricks"),
    "Robinhood":    ("greenhouse", "robinhood"),
    "Notion":       ("greenhouse", "notion"),
    "Datadog":      ("greenhouse", "datadoghq"),
    "Instacart":    ("greenhouse", "instacart"),
    "OpenAI":       ("greenhouse", "openai"),
    "Scale AI":     ("greenhouse", "scaleai"),
    "Chime":        ("greenhouse", "chime"),
    "Plaid":        ("greenhouse", "plaid"),
    "Coursera":     ("greenhouse", "coursera"),
    "Flexport":     ("greenhouse", "flexport"),
    "Patreon":      ("greenhouse", "patreon"),
    "Chainalysis":  ("greenhouse", "chainalysis"),
    "DigitalOcean": ("greenhouse", "digitalocean"),
    "Andela":       ("greenhouse", "andela"),
    "Affirm":       ("greenhouse", "affirm"),
    "CrowdStrike":  ("greenhouse", "crowdstrike"),
    "MongoDB":      ("greenhouse", "mongodb"),
    "OpenSea":      ("greenhouse", "opensea"),
    "Mistral":      ("greenhouse", "mistral"),
    # Lever
    "Lyft":         ("lever", "lyft"),
    "Snap":         ("lever", "snap"),
    "Snapchat":     ("lever", "snap"),
    "Anduril":      ("lever", "anduril"),
    "Grab":         ("lever", "grab"),
    "Spotify":      ("lever", "spotify"),
    "Peloton":      ("lever", "peloton"),
    "Atlassian":    ("lever", "atlassian"),
}


def _headers() -> dict:
    return {"User-Agent": "PulseBoard kianhaghighics@gmail.com"}


def fetch_greenhouse_count(slug: str) -> int | None:
    url = f"{GREENHOUSE_BASE}/{slug}/jobs?content=false"
    try:
        resp = requests.get(url, headers=_headers(), timeout=15)
        if resp.ok:
            return len(resp.json().get("jobs", []))
    except Exception:
        pass
    return None


def fetch_lever_count(slug: str) -> int | None:
    url = f"{LEVER_BASE}/{slug}?mode=json&limit=500"
    try:
        resp = requests.get(url, headers=_headers(), timeout=15)
        if resp.ok:
            data = resp.json()
            if isinstance(data, list):
                return len(data)
    except Exception:
        pass
    return None


def refresh_company_jobs(
    company_name: str,
    ats_type: str,
    ats_slug: str,
    public_company_id: int | None = None,
) -> bool:
    from ..models.models import JobPostingCount

    if ats_type == "greenhouse":
        count = fetch_greenhouse_count(ats_slug)
    elif ats_type == "lever":
        count = fetch_lever_count(ats_slug)
    else:
        return False

    if count is None:
        return False

    today = date.today()
    snap = JobPostingCount.query.filter_by(
        company_name=company_name, snapshot_date=today
    ).first()
    if snap:
        snap.posting_count = count
    else:
        snap = JobPostingCount(
            company_name=company_name,
            public_company_id=public_company_id,
            snapshot_date=today,
            posting_count=count,
            ats_type=ats_type,
            ats_slug=ats_slug,
        )
        db.session.add(snap)
    db.session.commit()
    return True


def refresh_all_jobs() -> dict:
    from ..models.models import PublicCompany

    results = {}
    for company_name, (ats_type, ats_slug) in ATS_MAPPING.items():
        pc = PublicCompany.query.filter_by(name=company_name).first()
        results[company_name] = refresh_company_jobs(
            company_name, ats_type, ats_slug,
            public_company_id=pc.id if pc else None,
        )
        time.sleep(0.2)
    return results


def get_latest_count(company_name: str):
    from ..models.models import JobPostingCount
    return (
        JobPostingCount.query
        .filter_by(company_name=company_name)
        .order_by(JobPostingCount.snapshot_date.desc())
        .first()
    )


def get_mom_change(company_name: str) -> float | None:
    from ..models.models import JobPostingCount

    latest = (
        JobPostingCount.query
        .filter_by(company_name=company_name)
        .order_by(JobPostingCount.snapshot_date.desc())
        .first()
    )
    if not latest:
        return None

    cutoff = latest.snapshot_date - timedelta(days=28)
    prior = (
        JobPostingCount.query
        .filter_by(company_name=company_name)
        .filter(JobPostingCount.snapshot_date <= cutoff)
        .order_by(JobPostingCount.snapshot_date.desc())
        .first()
    )
    if not prior or prior.posting_count == 0:
        return None

    return (latest.posting_count - prior.posting_count) / prior.posting_count * 100
