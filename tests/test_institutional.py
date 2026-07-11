import unittest
from unittest.mock import patch, MagicMock
from app import create_app
from app.extensions import db
from app.config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    AUTH0_DOMAIN = "test.auth0.com"
    AUTH0_CLIENT_ID = "test-client-id"
    AUTH0_CLIENT_SECRET = "test-secret"
    WTF_CSRF_ENABLED = False


SUBMISSIONS_JSON = {
    "filings": {
        "recent": {
            "form": ["13F-HR", "13F-NT"],
            "accessionNumber": ["0001193125-26-226661", "0001193125-25-000001"],
            "filingDate": ["2026-05-15", "2025-02-01"],
            "reportDate": ["2026-03-31", "2024-12-31"],
            "primaryDocument": ["xslForm13F_X02/primary_doc.xml", "primary_doc.xml"],
        }
    }
}

INDEX_JSON = {
    "directory": {
        "item": [
            {"name": "0001193125-26-226661-index.html", "size": ""},
            {"name": "primary_doc.xml", "size": "5555"},
            {"name": "53405.xml", "size": "45259"},
        ]
    }
}

# Two infoTable rows share a CUSIP (simulating a combination filer splitting a
# position across sub-managers) and must aggregate into a single holding.
INFOTABLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>037833100</cusip>
    <value>40000000000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>150000000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>037833100</cusip>
    <value>10000000000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>37500000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>UNTRACKED CO</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>999999999</cusip>
    <value>5000000000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>1000000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
  </infoTable>
</informationTable>"""


def _mock_response(json_data=None, text_data=None, ok=True):
    resp = MagicMock()
    resp.ok = ok
    if json_data is not None:
        resp.json.return_value = json_data
    if text_data is not None:
        resp.text = text_data
    return resp


class InstitutionalTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_seed_managers_idempotent(self):
        from app.services.institutional import seed_managers, SEED_MANAGERS
        from app.models.models import InstitutionalManager

        seed_managers()
        seed_managers()
        self.assertEqual(InstitutionalManager.query.count(), len(SEED_MANAGERS))

    @patch("app.services.institutional.requests.get")
    def test_refresh_manager_parses_aggregates_and_upserts(self, mock_get):
        from app.models.models import InstitutionalManager, InstitutionalHolding
        from app.services.institutional import refresh_manager

        mock_get.side_effect = [
            _mock_response(json_data=SUBMISSIONS_JSON),
            _mock_response(json_data=INDEX_JSON),
            _mock_response(text_data=INFOTABLE_XML),
        ]

        manager = InstitutionalManager(name="Test Fund", cik="0009999901", manager_type="Hedge Fund")
        db.session.add(manager)
        db.session.commit()

        upserted = refresh_manager(manager)
        self.assertEqual(upserted, 2)  # two distinct CUSIPs after aggregation

        aapl_holding = InstitutionalHolding.query.filter_by(cusip="037833100").first()
        self.assertIsNotNone(aapl_holding)
        self.assertEqual(aapl_holding.value_usd, 50_000_000_000)  # 40B + 10B aggregated
        self.assertEqual(aapl_holding.shares, 187_500_000)
        self.assertEqual(str(aapl_holding.period_end), "2026-03-31")
        self.assertIsNotNone(manager.last_refreshed_at)

    @patch("app.services.institutional.requests.get")
    def test_refresh_manager_matches_public_company_by_cusip(self, mock_get):
        from app.models.models import InstitutionalManager, InstitutionalHolding, PublicCompany
        from app.services.institutional import refresh_manager

        mock_get.side_effect = [
            _mock_response(json_data=SUBMISSIONS_JSON),
            _mock_response(json_data=INDEX_JSON),
            _mock_response(text_data=INFOTABLE_XML),
        ]

        aapl = PublicCompany.query.filter_by(ticker="AAPL").first()
        aapl.cusip = "037833100"
        db.session.commit()

        manager = InstitutionalManager(name="Test Fund", cik="0009999901", manager_type="Hedge Fund")
        db.session.add(manager)
        db.session.commit()

        refresh_manager(manager)

        matched = InstitutionalHolding.query.filter_by(cusip="037833100").first()
        unmatched = InstitutionalHolding.query.filter_by(cusip="999999999").first()
        self.assertEqual(matched.public_company_id, aapl.id)
        self.assertIsNone(unmatched.public_company_id)

    @patch("app.services.institutional.requests.get")
    def test_refresh_manager_upsert_is_idempotent(self, mock_get):
        from app.models.models import InstitutionalManager, InstitutionalHolding
        from app.services.institutional import refresh_manager

        mock_get.side_effect = [
            _mock_response(json_data=SUBMISSIONS_JSON),
            _mock_response(json_data=INDEX_JSON),
            _mock_response(text_data=INFOTABLE_XML),
        ] * 2

        manager = InstitutionalManager(name="Test Fund", cik="0009999901", manager_type="Hedge Fund")
        db.session.add(manager)
        db.session.commit()

        refresh_manager(manager)
        refresh_manager(manager)

        self.assertEqual(InstitutionalHolding.query.filter_by(manager_id=manager.id).count(), 2)

    @patch("app.services.institutional.requests.get")
    def test_get_holders_for_company_orders_by_value(self, mock_get):
        from app.models.models import InstitutionalManager, PublicCompany
        from app.services.institutional import refresh_manager, get_holders_for_company

        aapl = PublicCompany.query.filter_by(ticker="AAPL").first()
        aapl.cusip = "037833100"
        db.session.commit()

        mgr_a = InstitutionalManager(name="Fund A", cik="0009999901", manager_type="Hedge Fund")
        mgr_b = InstitutionalManager(name="Fund B", cik="0009999902", manager_type="Hedge Fund")
        db.session.add_all([mgr_a, mgr_b])
        db.session.commit()

        mock_get.side_effect = [
            _mock_response(json_data=SUBMISSIONS_JSON),
            _mock_response(json_data=INDEX_JSON),
            _mock_response(text_data=INFOTABLE_XML),
            _mock_response(json_data=SUBMISSIONS_JSON),
            _mock_response(json_data=INDEX_JSON),
            _mock_response(text_data=INFOTABLE_XML),
        ]
        refresh_manager(mgr_a)
        refresh_manager(mgr_b)

        holders = get_holders_for_company(aapl.id)
        self.assertEqual(len(holders), 2)
        self.assertEqual(holders[0].value_usd, holders[1].value_usd)  # same fixture data
        self.assertEqual({h.manager.name for h in holders}, {"Fund A", "Fund B"})

    def test_institutional_index_route_returns_200(self):
        resp = self.client.get("/institutional/")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
