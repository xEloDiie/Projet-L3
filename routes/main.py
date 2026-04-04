from flask import Blueprint, render_template, session
from utils.user_context import prepare_base_context
from db.mongo import users_collection, users_progression_collection, challenges_collection

main_bp = Blueprint("main", __name__)

@main_bp.route("/dashboard")
def dashboard():
    base_ctx = prepare_base_context()

    challenges = list(challenges_collection.find())
    total_players = users_progression_collection.count_documents({})

    for c in challenges:
        c["id"] = str(c["_id"])

        solved_count = users_progression_collection.count_documents(
            {"solved_challenges": c["_id"]}
        )

        c["success_rate"] = round((solved_count / total_players) * 100, 1) if total_players > 0 else 0

    total = len(challenges)
    solved = len(base_ctx["solved_challenges"])
    progress = int((solved / total) * 100) if total > 0 else 0

    all_users = list(users_collection.find())

    top_players = []
    for user in all_users:
        prog = users_progression_collection.find_one({"user_id": user["_id"]})
        points = prog["points"] if prog else 0

        top_players.append({
            "username": user["username"],
            "points": points
        })

    top_players.sort(key=lambda x: x["points"], reverse=True)
    top_players = top_players[:5]

    success_message = session.pop('challenge_success', None)

    return render_template(
        "dashboard.html",
        challenges=challenges,
        total=total,
        solved=solved,
        progress=progress,
        top_players=top_players,
        challenge_success=success_message,
        **base_ctx
    )


@main_bp.route("/leaderboard")
def leaderboard():
    ranking = list(
        users_progression_collection.find().sort("points", -1)
    )

    leaderboard_data = []

    for entry in ranking:

        user = users_collection.find_one({"_id": entry["user_id"]})

        if user:
            leaderboard_data.append({
                "username": user["username"],
                "points": entry["points"],
                "solved": len(entry.get("solved_challenges", []))
            })

    return render_template(
        "leaderboard.html",
        leaderboard=leaderboard_data,
        **prepare_base_context()
    )

@main_bp.route("/mentions-legales")
def mentions_legales():
    return render_template("mentions_legales.html")

@main_bp.route("/conditions-utilisation")
def conditions_utilisation():
    return render_template("conditions_utilisation.html")

@main_bp.route("/rgpd")
def rgpd():
    return render_template("rgpd.html")