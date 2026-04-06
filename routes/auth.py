from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from db.mongo import users_collection, roles_collection, users_progression_collection, logs_collection
from datetime import datetime, timezone
import secrets, pyotp, random, re, threading
from flask_mail import Message
from config import Config
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from utils.security import limiter

ph = PasswordHasher()

auth_bp = Blueprint("auth", __name__)

# Pour gérer le next_id
last_user = users_collection.find_one(sort=[("_id", -1)])
next_id = last_user["_id"] + 1 if last_user and isinstance(last_user["_id"], int) else 1


# ROUTES AUTH

# Fonction utilitaire : conversion ISO -> UTC datetime
def to_utc(dt):
    if not dt:
        return None

    # Si c'est une string -> ISO
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)

    # Si pas de timezone -> on force UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


@auth_bp.route("/login", methods=["GET", "POST"])
#@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        username_lower = username.lower()
        password = request.form["password"].strip()

        # Recherche insensible à la casse
        user = users_collection.find_one({"username_lower": username_lower})
        now = datetime.now(timezone.utc)

        # Mauvais identifiants
        if not user:
            flash("Identifiants incorrects.")
            return redirect(url_for("auth.login"))

        try:
            # Tentative avec Argon2
            ph.verify(user["password"], password)

            # Rehash si nécessaire
            if ph.check_needs_rehash(user["password"]):
                new_hash = ph.hash(password)
                users_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"password": new_hash}}
                )

        except (VerifyMismatchError, InvalidHashError):
            # Fallback anciens mots de passe (plaintext)
            if user["password"] != password:
                flash("Identifiants incorrects.")
                return redirect(url_for("auth.login"))
            else:
                # Migration vers Argon2
                new_hash = ph.hash(password)
                users_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"password": new_hash}}
                )

        # Compte non vérifié
        if not user.get("email_verified", False):
            # Générer un nouveau token si besoin
            verification_token = user.get("verification_token") or secrets.token_urlsafe(32)
            
            if not user.get("verification_token"):
                users_collection.update_one({"_id": user["_id"]}, {"$set": {"verification_token": verification_token}})
                user["verification_token"] = verification_token
            
            send_verification_email(user)
            
            flash("Votre compte doit être activé. Un email de vérification vous a été envoyé.")
            return redirect(url_for("auth.login"))

        # Vérifier si la session est encore active
        last_active_str = session.get("last_active")
        session_valid = False

        if last_active_str:
            try:
                last_active = datetime.fromisoformat(last_active_str)
                if last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=timezone.utc)

                if now - last_active < Config.SESSION_TIMEOUT:
                    session_valid = True
            except:
                pass

        # Vérification du dernier 2FA validé
        last_2fa_validated = user.get("last_2fa_validated")
        if last_2fa_validated:
            if last_2fa_validated.tzinfo is None:
                last_2fa_validated = last_2fa_validated.replace(tzinfo=timezone.utc)
            if now - last_2fa_validated < Config.TWO_FA_VALIDITY:
                # Connexion directe, pas de nouveau code 2FA
                session["user_id"] = user["_id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                session["last_active"] = now.isoformat()

                logs_collection.insert_one({
                    "timestamp": now,
                    "username": user["username"],
                    "action": "login",
                    "details": "Connexion avec dernier code 2FA valide"
                })

                return redirect(url_for("main.dashboard"))
            
        # Anti-spam envoi code
        last_email_sent = session.get("email_2fa_last_sent")

        if last_email_sent:
            try:
                last_email_sent_dt = datetime.fromisoformat(last_email_sent)
                if last_email_sent_dt.tzinfo is None:
                    last_email_sent_dt = last_email_sent_dt.replace(tzinfo=timezone.utc)
                
                if now - last_email_sent_dt < Config.EMAIL_RESEND_COOLDOWN:
                    flash("Un code a déjà été envoyé récemment.")
                    
                    # Stockage temporaire pour auth2fa
                    session["pre_2fa_user_id"] = user["_id"]
                    session["pre_2fa_username"] = user["username"]
                    session["pre_2fa_role"] = user["role"]
                    
                    return redirect(url_for("auth.auth2fa"))
            except:
                pass

        # Génération et envoi du code 2FA
        verification_code = f"{random.randint(0, 999999):06d}"
        
        session["email_2fa_code"] = verification_code
        session["email_2fa_time"] = now.isoformat()
        session["email_2fa_last_sent"] = now.isoformat()
        
        session["pre_2fa_user_id"] = user["_id"]
        session["pre_2fa_username"] = user["username"]
        session["pre_2fa_role"] = user["role"]
        
        # Envoi par email
        msg = Message(
            subject="Votre code de connexion 404HackNotFound",
            recipients=[user["email"]],
            body=f"Bonjour {user['username']} !\nVoici votre code de connexion : {verification_code}"
        )

        try:
            send_email(msg)
            flash("Un code d'authentification vous a été envoyé par e-mail.")
        except Exception as e:
            print("Erreur reset_password mail:", e)
            flash("Impossible d'envoyer l'email de réinitialisation pour le moment.")
            return redirect(url_for("auth.login"))

        # Redirige vers la page pour saisir le code
        return redirect(url_for("auth.auth2fa"))

    # GET
    return render_template("login.html")


def is_valid_email(email):
    return re.match(r"^[^@]+@[^@]+\.[^@]+$", email)


def is_valid_username(username):
    return len(username) <= 20 and re.match(r"^[A-Za-z0-9_.-]+$", username)


def is_strong_password(password):
    return (
        8 <= len(password) <= 64
        and re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"\d", password) # Au moins 1 chiffre
        and re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)
    )


@auth_bp.route("/register", methods=["GET", "POST"])
#@limiter.limit("10 per minute", methods=["POST"])
def register():
    global next_id

    if request.method == "POST":
        username = request.form["username"].strip()
        username_lower = username.lower()
        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()

        # Vérification si l'email est valide
        if not is_valid_email(email):
            flash("Adresse e-mail invalide.")
            return redirect(url_for("auth.register"))

        # Vérifier si le nom d'utilisateur est valide
        if not is_valid_username(username):
            flash("Le nom d'utilisateur doit contenir au maximum 20 caractères et uniquement des lettres, des chiffres ou les caractères '.', '_' et '-'.")
            return redirect(url_for("auth.register"))

        # Vérification si le mot de passe est valide
        if not is_strong_password(password):
            flash("Mot de passe trop faible/invalide ou supérieur à 64 caractères.")
            return redirect(url_for("auth.register"))

        # Vérification si le username existe déjà
        if users_collection.find_one({"username_lower": username_lower}):
            flash("Nom d'utilisateur déjà utilisé.")
            return redirect(url_for("auth.register"))

        # Vérification si le mail existe déjà
        if users_collection.find_one({"email": email}):
            flash("Adresse e-mail déjà utilisée pour un autre compte.")
            return redirect(url_for("auth.register"))

        user_role = roles_collection.find_one({"role_name": "membre"})

        verification_token = secrets.token_urlsafe(32)
        totp_secret = pyotp.random_base32()

        user = {
            "_id": next_id,
            "username": username,              # version originale
            "username_lower": username_lower,  # version normalisée pour comparaison
            "email": email,
            "password": ph.hash(password),
            "role": user_role["role_name"],
            "verification_token": verification_token,
            "email_verified": False,
            "totp_secret": totp_secret
        }

        try:
            # INSERTION DIRECTE
            users_collection.insert_one(user)

            # Envoi email en async
            send_verification_email(user)

            users_progression_collection.insert_one({
                "user_id": user["_id"],
                "solved_challenges": [],
                "points": 0
            })

            logs_collection.insert_one({
                "timestamp": datetime.now(),
                "username": username,
                "action": "Création de compte",
                "details": f"Utilisateur '{username}' a créé un compte."
            })

            next_id += 1

            flash("Compte créé avec succès, vérifiez votre e-mail.")
            return redirect(url_for("auth.login"))

        except Exception as e:
            print("ERREUR REGISTER:", repr(e))
            flash("Erreur lors de la création du compte.")
            return redirect(url_for("auth.register"))

    return render_template("register.html")


def send_email(msg):
    app = current_app._get_current_object()

    def task():
        with app.app_context():
            try:
                mail = app.extensions.get('mail')
                mail.send(msg)
            except Exception as e:
                print("ERREUR SMTP:", e)

    threading.Thread(target=task).start()


def send_verification_email(user):
    token = user['verification_token']
    verify_url = f"https://four04hacknotfound.onrender.com/auth/verify_email/{token}"

    msg = Message(
        subject="Vérifiez votre email pour 404HackNotFound",
        recipients=[user['email']],
        body=f"Bonjour {user['username']} !\nCliquez ici : {verify_url}"
    )

    send_email(msg)


@auth_bp.route("/auth/verify_email/<token>")
def verify_email(token):
    user = users_collection.find_one({"verification_token": token})
    
    if not user:
        flash("Token invalide ou expiré.")
        return redirect(url_for("auth.login"))
    
    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"email_verified": True}, "$unset": {"verification_token": ""}}
    )

    flash("Email vérifié avec succès ! Vous pouvez maintenant vous connecter.")
    return redirect(url_for("auth.login"))


@auth_bp.route("/auth2fa", methods=["GET", "POST"])
def auth2fa():
    print("DEBUG AUTH2FA SESSION:", dict(session))
    # Vérifie qu'un utilisateur est en cours de pré-auth
    pre_user_id = session.get("pre_2fa_user_id")
    if not pre_user_id:
        flash("Veuillez vous connecter d'abord.")
        return redirect(url_for("auth.login"))

    user = users_collection.find_one({"_id": pre_user_id})
    if not user:
        flash("Utilisateur introuvable.")
        session.clear()
        return redirect(url_for("auth.login"))

    now = datetime.now(timezone.utc)


    # Vérifie si le code email est encore valide
    def is_email_code_valid(code_input):
        email_code = session.get("email_2fa_code")
        email_time = to_utc(session.get("email_2fa_time"))
        if email_code and email_time and (now - email_time <= Config.EMAIL_CODE_TIMEOUT):
            return code_input == email_code
        return False

    # GET : affiche le formulaire
    if request.method == "GET":
        return render_template("auth2fa.html")

    # POST : vérifie le code soumis
    code_input = request.form.get("code_2fa", "").strip()

    totp_secret = user.get("totp_secret")
    totp_valid = pyotp.TOTP(totp_secret).verify(code_input) if totp_secret else False
    email_valid = is_email_code_valid(code_input)

    if totp_valid or email_valid:
        # Auth complète
        session["user_id"] = user["_id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["last_active"] = now.isoformat()

        # Nettoyage de la pré-session
        for key in ["pre_2fa_user_id", "pre_2fa_username", "pre_2fa_role", "email_2fa_code", "email_2fa_time"]:
            session.pop(key, None)

        # Mise à jour last_2fa_validated en DB
        users_collection.update_one({"_id": user["_id"]}, {"$set": {"last_2fa_validated": now}})

        # Log connexion
        logs_collection.insert_one({
            "timestamp": now,
            "username": user["username"],
            "action": "login",
            "details": "Connexion réussie via 2FA"
        })

        return redirect(url_for("main.dashboard"))

    else:
        flash("Code incorrect ou expiré. Veuillez réessayer.")
        return redirect(url_for("auth.auth2fa"))


@auth_bp.route("/resend_2fa_code", methods=["POST"])
#@limiter.limit("5 per minute")
def resend_2fa_code():
    print("DEBUG SESSION:", dict(session))
    if "pre_2fa_user_id" not in session:
        flash("Veuillez vous reconnecter pour recevoir un nouveau code.")
        return redirect(url_for("auth.login"))

    user = users_collection.find_one({"_id": session["pre_2fa_user_id"]})
    if not user:
        flash("Utilisateur introuvable.")
        return redirect(url_for("auth.login"))

    now = datetime.now(timezone.utc)
    last_email_sent = session.get("email_2fa_last_sent")
    if last_email_sent and (now - datetime.fromisoformat(last_email_sent)) < Config.EMAIL_RESEND_COOLDOWN:
        flash("Veuillez attendre un moment avant de demander un nouveau code.")
        return redirect(url_for("auth.auth2fa"))

    # Générer un nouveau code
    new_code = f"{random.randint(0, 999999):06d}"
    session["email_2fa_code"] = new_code
    session["email_2fa_time"] = now.isoformat()
    session["email_2fa_last_sent"] = now.isoformat()

    # Envoyer l’email
    msg = Message(
        subject="Votre code de connexion 404HackNotFound",
        recipients=[user["email"]],
        body=f"Bonjour {user['username']} !\nVoici votre code de connexion : {new_code}"
    )

    try:
        send_email(msg)
        flash("Un nouveau code a été envoyé par email.")
    except Exception as e:
        print("ERREUR SMTP RESET:", e)
        flash("Impossible d'envoyer l'email pour le moment.")
        return redirect(url_for("auth.login"))

    return redirect(url_for("auth.auth2fa"))


@auth_bp.route("/forgot_password", methods=["GET", "POST"])
#@limiter.limit("5 per minute", methods=["POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = users_collection.find_one({"email": email})

        if user:
            token = secrets.token_urlsafe(32)
            expiry = datetime.now(timezone.utc) + Config.EMAIL_CODE_TIMEOUT

            users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {
                    "reset_token": token,
                    "reset_token_expiry": expiry
                }}
            )

            reset_url = f"https://four04hacknotfound.onrender.com/reset_password/{token}"

            msg = Message(
                subject="Réinitialisation de votre mot de passe",
                recipients=[email],
                body=f"Bonjour {user['username']} !\nCliquez ici pour réinitialiser votre mot de passe : {reset_url}"
            )

            try:
                send_email(msg)
            except Exception as e:
                print("ERREUR SMTP RESET:", e)
                flash("Impossible d'envoyer l'email pour le moment.")
                return redirect(url_for("auth.login"))

        # sécurité : ne pas dire si email existe
        flash("Si un compte existe avec cet email, un lien a été envoyé.")
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


@auth_bp.route("/reset_password/<token>", methods=["GET", "POST"])
#@limiter.limit("5 per minute", methods=["POST"])
def reset_password(token):
    user = users_collection.find_one({"reset_token": token})

    if not user:
        flash("Lien invalide.")
        return redirect(url_for("auth.login"))

    expiry = to_utc(user.get("reset_token_expiry"))

    if not expiry or datetime.now(timezone.utc) > expiry:
        flash("Lien invalide ou expiré.")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form["password"].strip()

        if not is_strong_password(password):
            flash("Mot de passe trop faible/invalide ou supérieur à 64 caractères.")
            return redirect(request.url)

        new_hash = ph.hash(password)

        users_collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {"password": new_hash},
                "$unset": {"reset_token": "", "reset_token_expiry": ""}
            }
        )

        flash("Mot de passe mis à jour.")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html")


@auth_bp.route("/guest_login")
def guest_login():
    visitor_role = roles_collection.find_one({"role_name": "visiteur"})

    if not visitor_role:
        flash("Rôle invité introuvable.")
        return redirect(url_for("auth.login"))

    session.clear()

    session["role"] = visitor_role["role_name"]
    session["username"] = "Invité"
    session["last_active"] = datetime.now(timezone.utc).isoformat()

    return redirect(url_for("main.dashboard"))


@auth_bp.route("/logout")
def logout():
    if "username" in session:
        logs_collection.insert_one({
            "timestamp": datetime.now(timezone.utc),
            "username": session.get("username"),
            "action": "logout",
            "details": "Déconnexion manuelle"
        })

    session.clear()
    return redirect(url_for("auth.login"))