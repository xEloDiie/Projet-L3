import os
from datetime import timedelta
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")

    # Flask-Mail
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 25))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS") == "True"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL") == "True"
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")
    MAIL_TIMEOUT = 20

    # Fuseau horaire
    TIMEZONE = ZoneInfo("Europe/Paris")  # CET/CEST automatique

    # Durées et timeouts
    SESSION_TIMEOUT = timedelta(minutes=15)       # Timeout session
    EMAIL_CODE_TIMEOUT = timedelta(minutes=15)    # Code email
    TWO_FA_VALIDITY = timedelta(hours=24)         # Validité du 2FA sans renvoi de code
    EMAIL_RESEND_COOLDOWN = timedelta(seconds=30) # Anti-spam envoi email

    # Rate limit
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI")
    RATELIMIT_STRATEGY = "fixed-window"