import unittest
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


class FeedTestCase(unittest.TestCase):
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

    def test_feed_redirects_unauthenticated(self):
        resp = self.client.get("/")
        self.assertIn(resp.status_code, (302, 401))

    def test_like_requires_auth(self):
        resp = self.client.post("/like/1", json={"value": 1})
        self.assertIn(resp.status_code, (302, 401))


if __name__ == "__main__":
    unittest.main()
