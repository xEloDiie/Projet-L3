from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db.mongo import challenges_collection, users_progression_collection, logs_collection
from utils.user_context import prepare_base_context
from datetime import datetime

challenges_bp = Blueprint("challenges", __name__)

@challenges_bp.route("/challenge/<int:id>")
def challenge_page(id):
    # Bloquer les visiteurs
    if "user_id" not in session:
        flash("Vous devez créer un compte pour accéder aux challenges.")
        return redirect(url_for("auth.register"))

    challenge = challenges_collection.find_one({"_id": id})
    if not challenge:
        flash("Challenge introuvable.")
        return redirect(url_for("main.dashboard"))

    base_ctx = prepare_base_context()

    user_id = session.get("user_id")
    solved = False

    user_prog = users_progression_collection.find_one({"user_id": user_id})
    if user_prog:
        solved = id in user_prog.get("solved_challenges", [])

    template_name = f"challenges/challenge{id}.html"

    return render_template(
        template_name,
        challenge=challenge,
        solved=solved,
        **base_ctx
    )

@challenges_bp.route("/challenge/<int:id>/submit", methods=["POST"])
def submit_flag(id):
    # Sécurité
    if "user_id" not in session:
        flash("Vous devez être connecté pour soumettre un flag.")
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]

    challenge = challenges_collection.find_one({"_id": id})
    if not challenge:
        flash("Challenge introuvable.")
        return redirect(url_for("main.dashboard"))

    submitted_flag = request.form.get("flag", "").strip()

    user_prog = users_progression_collection.find_one({"user_id": user_id})

    # Créer progression si inexistante
    if not user_prog:
        users_progression_collection.insert_one({
            "user_id": user_id,
            "points": 0,
            "solved_challenges": []
        })
        user_prog = {
            "points": 0,
            "solved_challenges": []
        }

    solved_challenges = user_prog.get("solved_challenges", [])

    if submitted_flag == challenge["flag"]:
        if id not in solved_challenges:
            users_progression_collection.update_one(
                {"user_id": user_id},
                {
                    "$push": {"solved_challenges": id},
                    "$inc": {"points": challenge["points"]}
                }
            )

            logs_collection.insert_one({
                "timestamp": datetime.now(),
                "username": session.get("username"),
                "action": "Challenge résolu",
                "details": f"Challenge '{challenge['title']}' résolu par {session.get('username')}."
            })

            session['challenge_success'] = f"✅ Challenge '{challenge['title']}' résolu !"
            return redirect(url_for("main.dashboard"))

        else:
            flash("Vous avez déjà résolu ce challenge.")
    else:
        flash("Flag incorrect.")

    return redirect(url_for("challenges.challenge_page", id=id))