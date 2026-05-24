from flask import Blueprint, redirect, url_for, session, current_app, request
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
    print("[DEBUG] Login route called")
    print(f"[DEBUG] Session type: {current_app.config.get('SESSION_TYPE')}")
    print(f"[DEBUG] SECRET_KEY set: {bool(current_app.config.get('SECRET_KEY'))}")
    print(f"[DEBUG] Session before authorize: {dict(session)}")
    print(f"[DEBUG] Session ID: {session.get('_id', 'NO ID')}")
    print(f"[DEBUG] Redirect URI: {current_app.config['AUTH0_CALLBACK_URL']}")
    result = oauth.auth0.authorize_redirect(redirect_uri=current_app.config["AUTH0_CALLBACK_URL"])
    print(f"[DEBUG] Session after authorize: {dict(session)}")
    return result


@auth_bp.route("/callback")
def callback():
    print("[DEBUG] Callback route called")
    print(f"[DEBUG] Session on callback: {dict(session)}")
    print(f"[DEBUG] Session ID on callback: {session.get('_id', 'NO ID')}")
    print(f"[DEBUG] Request args: {dict(request.args)}")
    try:
        token = oauth.auth0.authorize_access_token()
        print(f"[DEBUG] Token received: {token}")
        userinfo = token["userinfo"]
        print(f"[DEBUG] User info: {userinfo}")

        user = User.query.filter_by(auth0_id=userinfo["sub"]).first()
        print(f"[DEBUG] Existing user found: {user}")
        
        if not user:
            print(f"[DEBUG] Creating new user with auth0_id: {userinfo['sub']}")
            user = User(
                auth0_id=userinfo["sub"],
                email=userinfo.get("email", ""),
                name=userinfo.get("name", ""),
                avatar_url=userinfo.get("picture", ""),
            )
            db.session.add(user)
            db.session.commit()
            print(f"[DEBUG] New user created: {user.id}")

        login_user(user)
        print(f"[DEBUG] User {user.id} logged in successfully")
        return redirect(url_for("feed.index"))
    except Exception as e:
        print(f"[ERROR] Callback error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


@auth_bp.route("/logout")
def logout():
    print("[DEBUG] Logout route called")
    logout_user()
    session.clear()
    logout_url = (
        f'https://{current_app.config["AUTH0_DOMAIN"]}/v2/logout'
        f'?returnTo={url_for("feed.index", _external=True)}'
        f'&client_id={current_app.config["AUTH0_CLIENT_ID"]}'
    )
    print(f"[DEBUG] Redirecting to logout URL: {logout_url}")
    return redirect(logout_url)
