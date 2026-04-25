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


class IngestionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    @patch("app.services.ingestion.feedparser.parse")
    def test_ingest_rss_adds_articles(self, mock_parse):
        mock_parse.return_value = MagicMock(
            feed=MagicMock(title="TechCrunch"),
            entries=[
                MagicMock(
                    link="https://example.com/article-1",
                    title="Startup raises $10M",
                    summary="A startup raised money.",
                    published_parsed=(2024, 1, 15, 12, 0, 0, 0, 0, 0),
                )
            ],
        )
        from app.services.ingestion import ingest_rss
        added = ingest_rss()
        self.assertEqual(added, len(RSS_FEEDS := [1]))  # one feed mocked

    @patch("app.services.ingestion.feedparser.parse")
    def test_ingest_rss_deduplicates(self, mock_parse):
        mock_parse.return_value = MagicMock(
            feed=MagicMock(title="TechCrunch"),
            entries=[
                MagicMock(
                    link="https://example.com/article-1",
                    title="Startup raises $10M",
                    summary="A startup raised money.",
                    published_parsed=(2024, 1, 15, 12, 0, 0, 0, 0, 0),
                )
            ],
        )
        from app.services.ingestion import ingest_rss
        ingest_rss()
        added_second = ingest_rss()
        self.assertEqual(added_second, 0)


if __name__ == "__main__":
    unittest.main()
