import os

# Dotenv pour Python
from dotenv import load_dotenv

# Flask
from flask import Flask, render_template, request, redirect, url_for, session, flash

# MongoDB
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Sécurité – hashage mot de passe
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Sécurité – chiffrement clé 2FA
from cryptography.fernet import Fernet

# 2FA – TOTP
import pyotp

# Protection brute-force
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Sécurisation des en-têtes HTTP
from flask_talisman import Talisman

# Tests unitaires
import unittest

# Charger les variables du .env
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# Créer le client
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))

# Sélectionner la base 404HackNotFound
db = client["404HackNotFound"]

# Collections
users_collection = db["users"]
roles_collection = db["roles"]
challenges_collection = db["challenges"]
users_progression_collection = db["users_progression"]

# Récupérer le plus grand _id actuel
last_user = users_collection.find_one(sort=[("_id", -1)])
next_id = last_user["_id"] + 1 if last_user and isinstance(last_user["_id"], int) else 1

# ======================
# FLASK APP
# ======================
app = Flask(__name__)
app.secret_key = "dev_secret_key"


@app.route("/")
def index():
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    global next_id

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if users_collection.find_one({"username": username}):
            flash("Nom d'utilisateur déjà utilisé.")
            return redirect(url_for("register"))

        user_role = roles_collection.find_one({"role_name": "user"})
        user = {
            "_id": next_id,
            "username": username,
            "password": password,
            "role": user_role["role_name"]
        }

        users_collection.insert_one(user)

        users_progression_collection.insert_one({
            "user_id": next_id,
            "solved_challenges": [],
            "points": 0
        })

        next_id += 1
        flash("Compte créé avec succès.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users_collection.find_one({"username": username})

        if user and user["password"] == password:
            session["user_id"] = user["_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        else:
            flash("Identifiants incorrects.")
            return redirect(url_for("login"))

    return render_template("login.html")


def prepare_base_context():

    if "user_id" in session:
        user_id = session["user_id"]
        user = users_collection.find_one({"_id": user_id})

        username = user["username"]
        role_name = user["role"]

        user_progress = users_progression_collection.find_one({"user_id": user_id})

        user_points = user_progress.get("points", 0) if user_progress else 0
        solved_challenges = user_progress.get("solved_challenges", []) if user_progress else []

        total_players = users_progression_collection.count_documents({})

        rank = None
        if total_players > 0:
            ranking = list(users_progression_collection.find().sort("points", -1))

            for i, entry in enumerate(ranking, start=1):
                if entry["user_id"] == user_id:
                    rank = i
                    break
        else:
            rank = 0

        challenges = list(challenges_collection.find())
        max_points = sum(c["points"] for c in challenges) if challenges else 0

    else:

        username = session.get("username", "Invité")
        role_name = session.get("role", "visitor")

        user_points = 0
        rank = 0
        total_players = 0
        max_points = 0
        solved_challenges = []

    return {
        "username": username,
        "role": role_name,
        "points": user_points,
        "rank": rank,
        "total_players": total_players,
        "max_points": max_points,
        "solved_challenges": solved_challenges
    }


@app.route("/dashboard")
def dashboard():

    base_ctx = prepare_base_context()

    role_doc = roles_collection.find_one({"role_name": base_ctx["role"]})
    permission = role_doc["permission"] if role_doc else 2

    challenges = list(challenges_collection.find())

    for c in challenges:
        c["id"] = str(c["_id"])

        total_players = base_ctx["total_players"]

        solved_count = users_progression_collection.count_documents(
            {"solved_challenges": c["_id"]}
        )

        c["success_rate"] = int((solved_count / total_players) * 100) if total_players > 0 else 0

    total = len(challenges)
    solved = len(base_ctx["solved_challenges"])

    progress = int((solved / total) * 100) if total > 0 else 0

    top_players_raw = list(
        users_progression_collection.find().sort("points", -1).limit(5)
    )

    top_players = []

    for entry in top_players_raw:
        user = users_collection.find_one({"_id": entry["user_id"]})

        if user:
            top_players.append({
                "username": user["username"],
                "points": entry["points"]
            })

    return render_template(
        "dashboard.html",
        permission=permission,
        challenges=challenges,
        total=total,
        solved=solved,
        progress=progress,
        top_players=top_players,
        **base_ctx
    )


@app.route("/admin/admin_challenges", methods=["GET", "POST"])
def admin_challenges():

    if "user_id" not in session:
        flash("Vous devez être connecté.")
        return redirect(url_for("login"))

    base_ctx = prepare_base_context()

    role_doc = roles_collection.find_one({"role_name": base_ctx["role"]})
    permission = role_doc["permission"] if role_doc else 2

    if permission != 0:
        flash("Accès refusé : réservé aux administrateurs.")
        return redirect(url_for("dashboard"))

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
        return redirect(url_for("admin_challenges"))

    challenges = list(challenges_collection.find())

    return render_template(
        "admin/admin_challenges.html",
        challenges=challenges,
        **base_ctx
    )


@app.route("/challenge/<int:id>")
def challenge_page(id):

    # 🔒 BLOQUER LES VISITEURS
    if session.get("role") == "visitor":
        flash("Vous devez créer un compte pour accéder aux challenges.")
        return redirect(url_for("register"))

    challenge = challenges_collection.find_one({"_id": id})

    if not challenge:
        flash("Challenge introuvable.")
        return redirect(url_for("dashboard"))

    base_ctx = prepare_base_context()

    user_id = session.get("user_id")

    solved = False

    if user_id:
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


@app.route("/challenge/<int:id>/submit", methods=["POST"])
def submit_flag(id):

    # 🔒 BLOQUER LES VISITEURS
    if session.get("role") == "visitor":
        flash("Vous devez créer un compte pour soumettre un flag.")
        return redirect(url_for("register"))

    if "user_id" not in session:
        flash("Vous devez être connecté pour soumettre un flag.")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    challenge = challenges_collection.find_one({"_id": id})

    if not challenge:
        flash("Challenge introuvable.")
        return redirect(url_for("dashboard"))

    submitted_flag = request.form.get("flag", "").strip()

    user_prog = users_progression_collection.find_one({"user_id": user_id})

    if not user_prog:
        flash("Erreur de progression utilisateur.")
        return redirect(url_for("dashboard"))

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

            flash("Félicitations ! Challenge résolu.")

        else:
            flash("Vous avez déjà résolu ce challenge.")

    else:
        flash("Flag incorrect.")

    return redirect(url_for("challenge_page", id=id))


@app.route("/leaderboard")
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


@app.route("/guest_login")
def guest_login():

    visitor_role = roles_collection.find_one({"role_name": "visitor"})

    if not visitor_role:
        flash("Rôle invité introuvable.")
        return redirect(url_for("login"))

    session.clear()

    session["role"] = visitor_role["role_name"]
    session["username"] = "Invité"

    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():

    session.clear()
    return redirect(url_for("login"))


# Vérifier la connexion MongoDB
try:
    client.admin.command('ping')
    print("Connexion à MongoDB réussie !")

except Exception as e:
    print("Erreur de connexion :", e)


if __name__ == "__main__":
    app.run(debug=True)