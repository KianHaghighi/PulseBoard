import time
import requests
from datetime import datetime, date, timezone
from ..extensions import db

EDGAR_BASE = "https://data.sec.gov"

REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
]
NET_INCOME_CONCEPTS = ["NetIncomeLoss"]
EPS_CONCEPTS = ["EarningsPerShareBasic"]
ASSETS_CONCEPTS = ["Assets"]
CASH_CONCEPTS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsAndShortTermInvestments",
]

SEED_COMPANIES = [
    {"ticker": "AAPL",  "name": "Apple Inc.",              "cik": "0000320193", "sector": "Consumer Tech"},
    {"ticker": "MSFT",  "name": "Microsoft Corp.",          "cik": "0000789019", "sector": "Enterprise Tech"},
    {"ticker": "GOOGL", "name": "Alphabet Inc.",            "cik": "0001652044", "sector": "Internet"},
    {"ticker": "AMZN",  "name": "Amazon.com Inc.",          "cik": "0001018724", "sector": "E-Commerce / Cloud"},
    {"ticker": "META",  "name": "Meta Platforms Inc.",      "cik": "0001326801", "sector": "Social Media"},
    {"ticker": "NVDA",  "name": "NVIDIA Corp.",             "cik": "0001045810", "sector": "Semiconductors"},
    {"ticker": "TSLA",  "name": "Tesla Inc.",               "cik": "0001318605", "sector": "EV / Energy"},
    {"ticker": "CRM",   "name": "Salesforce Inc.",          "cik": "0001108524", "sector": "Enterprise SaaS"},
    {"ticker": "PLTR",  "name": "Palantir Technologies",    "cik": "0001321655", "sector": "AI / Analytics"},
    {"ticker": "SNOW",  "name": "Snowflake Inc.",           "cik": "0001640147", "sector": "Data Cloud"},
]


def _headers():
    return {"User-Agent": "PulseBoard kianhaghighics@gmail.com"}


def _fetch_facts(cik: str) -> dict | None:
    url = f"{EDGAR_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        resp = requests.get(url, headers=_headers(), timeout=30)
        if resp.ok:
            return resp.json()
    except Exception:
        pass
    return None


def _extract(gaap: dict, concepts: list, unit: str = "USD") -> list[dict]:
    for concept in concepts:
        entries = gaap.get(concept, {}).get("units", {}).get(unit, [])
        if entries:
            return sorted(entries, key=lambda x: x.get("end", ""), reverse=True)
    return []


def _flow_entries(entries: list[dict], form: str) -> list[dict]:
    """Keep only pure-period entries (not cumulative YTD) from a specific form type."""
    seen_ends = set()
    result = []
    for e in entries:
        if e.get("form") != form:
            continue
        end, start = e.get("end", ""), e.get("start", "")
        if not start or not end or end in seen_ends:
            continue
        try:
            days = (date.fromisoformat(end) - date.fromisoformat(start)).days
            if form == "10-K" and 340 <= days <= 390:
                result.append(e)
                seen_ends.add(end)
            elif form == "10-Q" and 80 <= days <= 105:
                result.append(e)
                seen_ends.add(end)
        except ValueError:
            pass
    return result


def _instant_map(entries: list[dict]) -> dict:
    """Latest value per period_end for balance-sheet (instantaneous) items."""
    seen, result = set(), {}
    for e in sorted(entries, key=lambda x: x.get("end", ""), reverse=True):
        end = e.get("end", "")
        if end and end not in seen:
            seen.add(end)
            result[end] = e["val"]
    return result


def seed_companies():
    from ..models.models import PublicCompany
    for c in SEED_COMPANIES:
        if not PublicCompany.query.filter_by(ticker=c["ticker"]).first():
            db.session.add(PublicCompany(
                ticker=c["ticker"], name=c["name"],
                cik=c["cik"], sector=c["sector"],
            ))
    db.session.commit()


def refresh_company(company) -> int:
    from ..models.models import FinancialSnapshot
    facts = _fetch_facts(company.cik)
    if not facts:
        return 0

    gaap = facts.get("facts", {}).get("us-gaap", {})

    rev_all  = _extract(gaap, REVENUE_CONCEPTS)
    ni_all   = _extract(gaap, NET_INCOME_CONCEPTS)
    eps_all  = _extract(gaap, EPS_CONCEPTS, unit="USD/shares")
    assets_map = _instant_map(_extract(gaap, ASSETS_CONCEPTS))
    cash_map   = _instant_map(_extract(gaap, CASH_CONCEPTS))

    upserted = 0
    for form, period_type, limit in [("10-K", "annual", 4), ("10-Q", "quarterly", 8)]:
        rev_snaps = _flow_entries(rev_all, form)[:limit]
        ni_map  = {e["end"]: e["val"] for e in _flow_entries(ni_all, form)}
        eps_map = {e["end"]: e["val"] for e in _flow_entries(eps_all, form)}

        for e in rev_snaps:
            end_date = date.fromisoformat(e["end"])
            snap = FinancialSnapshot.query.filter_by(
                company_id=company.id, period_end=end_date, period_type=period_type
            ).first()
            if not snap:
                snap = FinancialSnapshot(
                    company_id=company.id,
                    period_end=end_date,
                    period_type=period_type,
                )
                db.session.add(snap)
            snap.fiscal_year   = e.get("fy")
            snap.fiscal_period = e.get("fp")
            snap.revenue       = e["val"]
            snap.net_income    = ni_map.get(e["end"])
            snap.eps_basic     = eps_map.get(e["end"])
            snap.total_assets  = assets_map.get(e["end"])
            snap.cash          = cash_map.get(e["end"])
            upserted += 1

    company.last_refreshed_at = datetime.now(timezone.utc)
    db.session.commit()
    return upserted


def refresh_all() -> dict:
    from ..models.models import PublicCompany
    results = {}
    for company in PublicCompany.query.all():
        results[company.ticker] = refresh_company(company)
        time.sleep(0.2)
    return results
