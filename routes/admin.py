from flask import Blueprint, render_template, request, redirect, url_for, flash
from db.mongo import challenges_collection, logs_collection
from utils.user_context import prepare_base_context

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/admin_challenges", methods=["GET", "POST"])
def admin_challenges():
    base_ctx = prepare_base_context()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        difficulty = request.form["difficulty"]
        points = int(request.form["points"])
        flag = request.form["flag"]

        new_challenge = {
            "_id": challenges_collection.count_documents({}) + 1,
            "title": title,
            "description": description,
            "difficulty": difficulty,
            "points": points,
            "flag": flag
        }

        challenges_collection.insert_one(new_challenge)

        flash("Challenge ajouté avec succès !")
        return redirect(url_for("admin.admin_challenges"))

    challenges = list(challenges_collection.find())

    return render_template(
        "admin/admin_challenges.html",
        challenges=challenges,
        **base_ctx
    )


@admin_bp.route("/admin/logs")
def logs():
    base_ctx = prepare_base_context()

    logs = list(logs_collection.find().sort("timestamp", -1))

    return render_template(
        "admin/logs.html",
        logs=logs,
        **base_ctx
    )