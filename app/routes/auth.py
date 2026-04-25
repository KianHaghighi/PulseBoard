from flask import Blueprint, redirect, url_for, session, current_app
from flask_login import login_user, logout_user
from authlib.integrations.flask_client import OAuth
from ..models.models import User
from ..extensions import db

auth_bp = Blueprint("auth", __name__)
oauth = OAuth()


def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        "auth0",
        client_id=app.config["AUTH0_CLIENT_ID"],
        client_secret=app.config["AUTH0_CLIENT_SECRET"],
        client_kwargs={"scope": "openid profile email"},
        server_metadata_url=f'https://{app.config["AUTH0_DOMAIN"]}/.well-known/openid-configuration',
    )


@auth_bp.route("/login")
def login():
    return oauth.auth0.authorize_redirect(redirect_uri=current_app.config["AUTH0_CALLBACK_URL"])


@auth_bp.route("/callback")
def callback():
    token = oauth.auth0.authorize_access_token()
    userinfo = token["userinfo"]

    user = User.query.filter_by(auth0_id=userinfo["sub"]).first()
    if not user:
        user = User(
            auth0_id=userinfo["sub"],
            email=userinfo.get("email", ""),
            name=userinfo.get("name", ""),
            avatar_url=userinfo.get("picture", ""),
        )
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return redirect(url_for("feed.index"))


@auth_bp.route("/logout")
def logout():
    logout_user()
    session.clear()
    return redirect(
        f'https://{current_app.config["AUTH0_DOMAIN"]}/v2/logout'
        f'?returnTo={url_for("feed.index", _external=True)}'
        f'&client_id={current_app.config["AUTH0_CLIENT_ID"]}'
    )
