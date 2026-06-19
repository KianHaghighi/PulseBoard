import unittest
from app import create_app
from app.extensions import db
from app.models.models import User, Article, Collection, CollectionItem
from app.config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"
    AUTH0_DOMAIN = "test.auth0.com"
    AUTH0_CLIENT_ID = "test-client-id"
    AUTH0_CLIENT_SECRET = "test-secret"
    SESSION_TYPE = "filesystem"
    WTF_CSRF_ENABLED = False


class ProfileTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Create a test user and log them in via Flask-Login session
        self.user = User(auth0_id="auth0|test", email="test@example.com", name="Test User")
        db.session.add(self.user)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.user.id)
            sess["_fresh"] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # --- /profile/ ---

    def test_index_shows_collections(self):
        db.session.add(Collection(user_id=self.user.id, name="My Reads"))
        db.session.commit()
        resp = self.client.get("/profile/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"My Reads", resp.data)

    def test_index_requires_auth(self):
        with self.client.session_transaction() as sess:
            sess.clear()
        resp = self.client.get("/profile/")
        self.assertIn(resp.status_code, (302, 401))

    # --- /profile/settings ---

    def test_settings_get(self):
        resp = self.client.get("/profile/settings")
        self.assertEqual(resp.status_code, 200)

    def test_settings_save_keywords(self):
        resp = self.client.post(
            "/profile/settings",
            data={"keywords": "AI, SaaS", "digest_enabled": "on"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        db.session.refresh(self.user)
        self.assertEqual(self.user.keywords, "AI, SaaS")
        self.assertTrue(self.user.digest_enabled)

    def test_settings_disable_digest(self):
        self.user.digest_enabled = True
        db.session.commit()
        # digest_enabled checkbox absent from form → False
        self.client.post("/profile/settings", data={"keywords": ""}, follow_redirects=True)
        db.session.refresh(self.user)
        self.assertFalse(self.user.digest_enabled)

    # --- /profile/collections/new ---

    def test_create_collection(self):
        resp = self.client.post(
            "/profile/collections/new",
            data={"name": "AI Research"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(Collection.query.filter_by(name="AI Research").first())

    def test_create_collection_blank_name_ignored(self):
        self.client.post("/profile/collections/new", data={"name": "   "})
        self.assertEqual(Collection.query.count(), 0)

    # --- /profile/collections/<id> ---

    def test_view_collection(self):
        col = Collection(user_id=self.user.id, name="Bookmarks")
        db.session.add(col)
        db.session.commit()
        resp = self.client.get(f"/profile/collections/{col.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Bookmarks", resp.data)

    def test_view_collection_shows_articles(self):
        col = Collection(user_id=self.user.id, name="Tech")
        article = Article(
            url_hash="abc123", url="https://example.com/a",
            title="Test Article", source="TechCrunch",
        )
        db.session.add_all([col, article])
        db.session.commit()
        db.session.add(CollectionItem(collection_id=col.id, article_id=article.id))
        db.session.commit()
        resp = self.client.get(f"/profile/collections/{col.id}")
        self.assertIn(b"Test Article", resp.data)

    def test_view_collection_other_user_returns_404(self):
        other = User(auth0_id="auth0|other", email="other@example.com")
        db.session.add(other)
        db.session.commit()
        col = Collection(user_id=other.id, name="Private")
        db.session.add(col)
        db.session.commit()
        resp = self.client.get(f"/profile/collections/{col.id}")
        self.assertEqual(resp.status_code, 404)

    # --- /profile/collections/<id>/delete ---

    def test_delete_collection(self):
        col = Collection(user_id=self.user.id, name="To Delete")
        db.session.add(col)
        db.session.commit()
        col_id = col.id
        resp = self.client.post(f"/profile/collections/{col_id}/delete", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(Collection.query.get(col_id))

    def test_delete_collection_other_user_returns_404(self):
        other = User(auth0_id="auth0|other2", email="other2@example.com")
        db.session.add(other)
        db.session.commit()
        col = Collection(user_id=other.id, name="Not Mine")
        db.session.add(col)
        db.session.commit()
        resp = self.client.post(f"/profile/collections/{col.id}/delete")
        self.assertEqual(resp.status_code, 404)

    # --- /profile/collections/<id>/remove/<article_id> ---

    def test_remove_article_from_collection(self):
        col = Collection(user_id=self.user.id, name="Saved")
        article = Article(
            url_hash="xyz789", url="https://example.com/b",
            title="Article B", source="VentureBeat",
        )
        db.session.add_all([col, article])
        db.session.commit()
        item = CollectionItem(collection_id=col.id, article_id=article.id)
        db.session.add(item)
        db.session.commit()

        resp = self.client.post(
            f"/profile/collections/{col.id}/remove/{article.id}",
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(CollectionItem.query.filter_by(
            collection_id=col.id, article_id=article.id
        ).first())

    def test_remove_article_other_user_collection_returns_404(self):
        other = User(auth0_id="auth0|other3", email="other3@example.com")
        db.session.add(other)
        db.session.commit()
        col = Collection(user_id=other.id, name="Theirs")
        article = Article(
            url_hash="aaa111", url="https://example.com/c",
            title="Article C", source="Sifted",
        )
        db.session.add_all([col, article])
        db.session.commit()
        item = CollectionItem(collection_id=col.id, article_id=article.id)
        db.session.add(item)
        db.session.commit()
        resp = self.client.post(f"/profile/collections/{col.id}/remove/{article.id}")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
