from flask import Flask, session, redirect, url_for, flash, request
from db.mongo import logs_collection
from flask_mail import Mail
from datetime import datetime, timezone

from routes.auth import auth_bp
from routes.main import main_bp
from routes.challenges import challenges_bp
from routes.admin import admin_bp

from config import Config
from utils.security import init_security

app = Flask(__name__)
app.config.from_object(Config)

# =========================
# SECURITY
# =========================
init_security(app)

# =========================
# MAIL
# =========================
mail = Mail(app)
app.mail = mail

# =========================
# BLUEPRINTS
# =========================
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(challenges_bp)
app.register_blueprint(admin_bp)


@app.route("/")
def home():
    return redirect(url_for("auth.login"))

@app.before_request
def global_security():

    endpoint = request.endpoint or ""

    public_routes = [
        'auth.login',
        'auth.register',
        'auth.auth2fa',
        'auth.verify_email',
        'auth.guest_login',
        'main.mentions_legales',
        'main.conditions_utilisation',
        'main.rgpd',
        'auth.forgot_password',
        'auth.reset_password',
        'auth.resend_2fa_code'
    ]

    # =========================
    # Autorisations de base
    # =========================
    if endpoint.startswith("static"):
        return

    if endpoint in public_routes:
        return

    # =========================
    # Stocker dernière page
    # =========================
    if not endpoint.startswith("admin."):
        session["last_page"] = request.url

    # =========================
    # Accès admin
    # =========================
    if endpoint.startswith("admin."):
        if session.get("role") != "admin":
            flash("Accès refusé.", "danger")
            return redirect(session.get("last_page", url_for("main.dashboard")))

    # =========================
    # Vérification connexion (hors invité)
    # =========================
    if "user_id" not in session and session.get("role") != "visitor":
        return redirect(url_for("auth.login"))

    # =========================
    # Timeout uniquement user
    # =========================
    if "user_id" in session:
        last_active_str = session.get("last_active")

        if last_active_str:
            try:
                last_active = datetime.fromisoformat(last_active_str)
                now = datetime.now(timezone.utc)

                if now - last_active > Config.SESSION_TIMEOUT:
                    logs_collection.insert_one({
                        "timestamp": now,
                        "username": session.get("username", "inconnu"),
                        "action": "logout",
                        "details": "Déconnexion automatique par inactivité"
                    })

                    flash("Vous avez été déconnecté pour inactivité.", "warning")
                    session.clear()
                    return redirect(url_for("auth.login"))

            except:
                session.clear()
                return redirect(url_for("auth.login"))

        session["last_active"] = datetime.now(timezone.utc).isoformat()


@app.template_filter('paris_time')
def paris_time_filter(dt):
    if not dt:
        return ""

    # Si pas de timezone → on considère UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Conversion vers Paris (auto +01 / +02)
    dt = dt.astimezone(app.config["TIMEZONE"])

    return dt.strftime("%d/%m/%Y %H:%M:%S")


@app.before_request
def store_last_page():
    endpoint = request.endpoint or ""

    # On ignore les routes admin pour éviter de stocker une page interdite
    if endpoint.startswith("admin."):
        return

    # On ignore les fichiers statiques
    if endpoint.startswith("static"):
        return

    # On stocke la page actuelle
    session["last_page"] = request.url


# Ignoré par Render avec utilisation de gunicorn
if __name__ == "__main__":
    app.run(debug=True)