import time
import requests
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from ..extensions import db

SEC_BASE = "https://data.sec.gov"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

# CIKs verified against SEC EDGAR company search (action=getcompany, type=13F-HR)
# and each confirmed to have a 13F-HR filing history via data.sec.gov/submissions.
SEED_MANAGERS = [
    {"name": "Berkshire Hathaway Inc", "cik": "0001067983", "manager_type": "Holding Company"},
    {"name": "Bridgewater Associates, LP", "cik": "0001350694", "manager_type": "Hedge Fund"},
    {"name": "ARK Investment Management LLC", "cik": "0001697748", "manager_type": "Mutual Fund"},
    {"name": "Renaissance Technologies LLC", "cik": "0001037389", "manager_type": "Hedge Fund"},
    {"name": "Coatue Management LLC", "cik": "0001135730", "manager_type": "Hedge Fund"},
    {"name": "Tiger Global Management LLC", "cik": "0001167483", "manager_type": "Hedge Fund"},
    {"name": "Citadel Advisors LLC", "cik": "0001423053", "manager_type": "Hedge Fund"},
    {"name": "Pershing Square Capital Management, L.P.", "cik": "0001336528", "manager_type": "Hedge Fund"},
    {"name": "Two Sigma Investments, LP", "cik": "0001179392", "manager_type": "Hedge Fund"},
    {"name": "Third Point LLC", "cik": "0001040273", "manager_type": "Hedge Fund"},
    {"name": "Appaloosa LP", "cik": "0001656456", "manager_type": "Hedge Fund"},
    {"name": "Duquesne Family Office LLC", "cik": "0001536411", "manager_type": "Family Office"},
]


def _headers() -> dict:
    return {"User-Agent": "PulseBoard kianhaghighics@gmail.com"}


def seed_managers():
    from ..models.models import InstitutionalManager
    for m in SEED_MANAGERS:
        if not InstitutionalManager.query.filter_by(cik=m["cik"]).first():
            db.session.add(InstitutionalManager(**m))
    db.session.commit()


# ---------------------------------------------------------------------------
# Filing discovery
# ---------------------------------------------------------------------------

def _latest_13f_accession(cik: str) -> dict | None:
    """Return {accession_number, filing_date, period_end, primary_document} for the
    most recent non-amendment 13F-HR filing, or None if unavailable."""
    url = f"{SEC_BASE}/submissions/CIK{cik}.json"
    try:
        resp = requests.get(url, headers=_headers(), timeout=30)
        if not resp.ok:
            return None
        recent = resp.json().get("filings", {}).get("recent", {})
    except Exception:
        return None

    forms = recent.get("form", [])
    best = None
    for i, form in enumerate(forms):
        if form != "13F-HR":
            continue
        filing_date = recent["filingDate"][i]
        if best is None or filing_date > best["filing_date"]:
            best = {
                "accession_number": recent["accessionNumber"][i],
                "filing_date": filing_date,
                "period_end": recent["reportDate"][i],
                "primary_document": recent["primaryDocument"][i],
            }
    return best


def _find_infotable_filename(cik_nolead: str, accession_nodash: str, primary_document: str) -> str | None:
    """Locate the information-table XML in the accession's file index. The holdings
    table is never the cover-page primaryDocument itself, and its filename varies by
    the filer's filing software (e.g. a numeric name, 'infotable.xml', etc.)."""
    url = f"{ARCHIVES_BASE}/{cik_nolead}/{accession_nodash}/index.json"
    try:
        resp = requests.get(url, headers=_headers(), timeout=30)
        if not resp.ok:
            return None
        items = resp.json().get("directory", {}).get("item", [])
    except Exception:
        return None

    primary_basename = primary_document.rsplit("/", 1)[-1]
    xml_items = [
        it for it in items
        if it.get("name", "").lower().endswith(".xml") and it.get("name") != primary_basename
    ]
    if not xml_items:
        return None

    # Prefer a name that self-describes as the holdings table.
    for it in xml_items:
        if "info" in it.get("name", "").lower():
            return it["name"]

    # Otherwise assume it's the largest remaining XML (cover-page files are small;
    # the holdings table scales with position count).
    def _size(it):
        try:
            return int(it.get("size") or 0)
        except ValueError:
            return 0

    return max(xml_items, key=_size)["name"]


def _fetch_infotable_xml(cik_nolead: str, accession_nodash: str, filename: str) -> str | None:
    url = f"{ARCHIVES_BASE}/{cik_nolead}/{accession_nodash}/{filename}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=30)
        if resp.ok:
            return resp.text
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _parse_infotable(xml_text: str) -> list[dict]:
    """Parse a 13F information table into aggregated per-(cusip, put_call) rows.

    Combination filers (e.g. Berkshire) report the same position split across
    multiple sub-managers as separate <infoTable> entries with the same CUSIP, so
    entries must be summed rather than upserted one-for-one.
    """
    root = ET.fromstring(xml_text)
    aggregated: dict[tuple, dict] = {}

    for info_table in root:
        if _local(info_table.tag) != "infoTable":
            continue

        fields: dict[str, str] = {}
        shares = None
        for child in info_table:
            name = _local(child.tag)
            if name == "shrsOrPrnAmt":
                for sub in child:
                    if _local(sub.tag) == "sshPrnamt":
                        shares = sub.text
            elif len(child) == 0:
                fields[name] = child.text

        cusip = fields.get("cusip")
        if not cusip:
            continue
        put_call = fields.get("putCall") or None
        value_raw = fields.get("value")
        key = (cusip, put_call)

        entry = aggregated.setdefault(key, {
            "issuer_name": fields.get("nameOfIssuer") or "",
            "cusip": cusip,
            "put_call": put_call,
            "value_usd": 0,
            "shares": 0,
        })
        if value_raw:
            # SEC's 13F XML technical spec (v2.0.0, effective for 2023+ filings) reports
            # <value> in actual USD, not thousands as the older paper-form convention had it.
            entry["value_usd"] += int(float(value_raw))
        if shares:
            entry["shares"] += int(float(shares))

    return list(aggregated.values())


# ---------------------------------------------------------------------------
# Refresh orchestration
# ---------------------------------------------------------------------------

def refresh_manager(manager) -> int:
    from ..models.models import InstitutionalHolding, PublicCompany

    accession = _latest_13f_accession(manager.cik)
    if not accession:
        return 0

    cik_nolead = manager.cik.lstrip("0") or "0"
    accession_nodash = accession["accession_number"].replace("-", "")

    infotable_filename = _find_infotable_filename(
        cik_nolead, accession_nodash, accession["primary_document"]
    )
    if not infotable_filename:
        return 0

    xml_text = _fetch_infotable_xml(cik_nolead, accession_nodash, infotable_filename)
    if not xml_text:
        return 0

    try:
        rows = _parse_infotable(xml_text)
    except ET.ParseError:
        return 0

    period_end = date.fromisoformat(accession["period_end"])
    filed_at = date.fromisoformat(accession["filing_date"])

    upserted = 0
    for row in rows:
        # Resolve the company match before touching `holding` so that a fresh insert
        # doesn't get flushed prematurely (autoflush) with its NOT NULL fields unset.
        company = PublicCompany.query.filter_by(cusip=row["cusip"]).first()

        holding = InstitutionalHolding.query.filter_by(
            manager_id=manager.id, cusip=row["cusip"],
            period_end=period_end, put_call=row["put_call"],
        ).first()
        if not holding:
            holding = InstitutionalHolding(
                manager_id=manager.id, cusip=row["cusip"],
                period_end=period_end, put_call=row["put_call"],
            )
            db.session.add(holding)

        holding.issuer_name = row["issuer_name"]
        holding.value_usd = row["value_usd"]
        holding.shares = row["shares"]
        holding.filed_at = filed_at
        holding.accession_number = accession["accession_number"]
        holding.public_company_id = company.id if company else None
        upserted += 1

    manager.last_refreshed_at = datetime.now(timezone.utc)
    db.session.commit()
    return upserted


def refresh_all() -> dict:
    from ..models.models import InstitutionalManager

    results = {}
    for manager in InstitutionalManager.query.all():
        results[manager.name] = refresh_manager(manager)
        time.sleep(0.3)
    return results


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_holders_for_company(public_company_id: int, limit: int = 20) -> list:
    from ..models.models import InstitutionalHolding, InstitutionalManager

    latest_period = (
        db.session.query(db.func.max(InstitutionalHolding.period_end))
        .filter(InstitutionalHolding.public_company_id == public_company_id)
        .scalar()
    )
    if not latest_period:
        return []

    return (
        InstitutionalHolding.query
        .join(InstitutionalManager)
        .filter(
            InstitutionalHolding.public_company_id == public_company_id,
            InstitutionalHolding.period_end == latest_period,
            InstitutionalHolding.put_call.is_(None),
        )
        .order_by(InstitutionalHolding.value_usd.desc())
        .limit(limit)
        .all()
    )


def get_qoq_change(manager_id: int, cusip: str) -> float | None:
    from ..models.models import InstitutionalHolding

    holdings = (
        InstitutionalHolding.query
        .filter_by(manager_id=manager_id, cusip=cusip, put_call=None)
        .order_by(InstitutionalHolding.period_end.desc())
        .limit(2)
        .all()
    )
    if len(holdings) < 2:
        return None

    latest, prior = holdings[0], holdings[1]
    if not prior.value_usd:
        return None
    return (latest.value_usd - prior.value_usd) / prior.value_usd * 100
