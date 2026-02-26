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

# Collection users
users_collection = db["users"]

# Collection roles
roles_collection = db["roles"]

# Récupérer le plus grand _id actuel
last_user = users_collection.find_one(sort=[("_id", -1)])

if last_user and isinstance(last_user["_id"], int):
    next_id = last_user["_id"] + 1
else:
    next_id = 1


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

        # Vérifier si username existe déjà
        existing_user = users_collection.find_one({"username": username})
        if existing_user:
            flash("Nom d'utilisateur déjà utilisé.")
            return redirect(url_for("register"))

        # Récupérer le rôle 'user' depuis la collection roles
        user_role = roles_collection.find_one({"role_name": "user"})

        # Création utilisateur
        user = {
            "_id": next_id,
            "username": username,
            "password": password,  # Argon2 plus tard
            "role": user_role["role_name"]  # 'user'
        }

        users_collection.insert_one(user)
        next_id += 1

        flash("Compte créé avec succès.")
        return redirect(url_for("register"))

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


@app.route("/dashboard")
def dashboard():
    # Vérifier si c'est un utilisateur connecté
    if "user_id" in session:
        user = users_collection.find_one({"_id": session["user_id"]})
        username = user["username"]
        role_name = user["role"]
    else:
        # Si c'est un guest
        username = session.get("username", "Invité")
        role_name = session.get("role", "visitor")
    
    # Récupérer la permission depuis la collection roles
    role_doc = roles_collection.find_one({"role_name": role_name})
    permission = role_doc["permission"] if role_doc else 2  # fallback visitor

    return render_template("dashboard.html", username=username, role=role_name, permission=permission)


@app.route("/guest_login")
def guest_login():
    # Récupérer le rôle visitor depuis la collection roles
    visitor_role = roles_collection.find_one({"role_name": "visitor"})
    if not visitor_role:
        flash("Rôle invité introuvable.")
        return redirect(url_for("login"))

    # Créer une session temporaire pour le visiteur
    session.clear()
    session["role"] = visitor_role["role_name"]
    session["username"] = "Invité"

    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# Vérifier la connexion MongoDB au lancement
try:
    client.admin.command('ping')
    print("Connexion à MongoDB réussie !")
except Exception as e:
    print("Erreur de connexion :", e)


if __name__ == "__main__":
    app.run(debug=True)
