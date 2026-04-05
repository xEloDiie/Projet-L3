import os
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask_wtf import CSRFProtect
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

ph = PasswordHasher()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

# Hashage du mot de passe
def hash_password(password):
    return ph.hash(password)

# Vérifier le mot de passe hashé
def verify_password(hash, password):
    try:
        return ph.verify(hash, password)
    except VerifyMismatchError:
        return False

# Sécurités Flask supplémentaires  
def init_security(app):
    # CSRF
    csrf.init_app(app)

    # HTTPS + headers sécurité
    csp = {
    "default-src": "'self'",

    "script-src": [
        "'self'",
        "https://cdn.jsdelivr.net",
        "'unsafe-inline'"
    ],

    "style-src": [
        "'self'",
        "https://cdn.jsdelivr.net",
        "'unsafe-inline'"
    ],

    "img-src": [
        "'self'",
        "data:"
    ]
}
    
    Talisman(app, content_security_policy=csp, force_https=not app.debug)

    # Rate limiting
    limiter.init_app(app)