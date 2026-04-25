from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models.models import Collection, CollectionItem
from ..extensions import db

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/")
@login_required
def index():
    collections = Collection.query.filter_by(user_id=current_user.id).all()
    return render_template("profile/index.html", collections=collections)


@profile_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        current_user.keywords = request.form.get("keywords", "")
        current_user.digest_enabled = "digest_enabled" in request.form
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("profile.settings"))
    return render_template("profile/settings.html")


@profile_bp.route("/collections/new", methods=["POST"])
@login_required
def new_collection():
    name = request.form.get("name", "").strip()
    if name:
        db.session.add(Collection(user_id=current_user.id, name=name))
        db.session.commit()
    return redirect(url_for("profile.index"))


@profile_bp.route("/collections/<int:collection_id>")
@login_required
def view_collection(collection_id):
    collection = Collection.query.filter_by(id=collection_id, user_id=current_user.id).first_or_404()
    items = CollectionItem.query.filter_by(collection_id=collection_id).order_by(CollectionItem.saved_at.desc()).all()
    return render_template("profile/collection.html", collection=collection, items=items)


@profile_bp.route("/collections/<int:collection_id>/delete", methods=["POST"])
@login_required
def delete_collection(collection_id):
    collection = Collection.query.filter_by(id=collection_id, user_id=current_user.id).first_or_404()
    db.session.delete(collection)
    db.session.commit()
    return redirect(url_for("profile.index"))
