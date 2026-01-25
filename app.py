<<<<<<< HEAD
# Flask
from flask import Flask, render_template, request, redirect, url_for, session, flash

# MongoDB
from pymongo import MongoClient

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
=======
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

# Créer la collection users (sera créée automatiquement si elle n'existe pas)
users_collection = db["users"]

# Récupérer le plus grand _id actuel
last_user = users_collection.find_one(sort=[("_id", -1)])

# Si le dernier utilisateur n'existe pas ou _id n'est pas numérique, commencer à 1
if last_user and isinstance(last_user["_id"], int):
    next_id = last_user["_id"] + 1
else:
    next_id = 1

# Exemple : créer un utilisateur
user = {
    "_id": next_id, # ID numérique
    "username": "testuser",
    "password": "hash_mot_de_passe", # à remplacer par Argon2 plus tard
    "role": "user"
}

# Insérer l'utilisateur
result = users_collection.insert_one(user)
print(f"Utilisateur inséré avec _id = {user['_id']}")

# Vérifier la connexion
try:
    client.admin.command('ping')
    print("Connexion à MongoDB réussie !")
except Exception as e:
    print("Erreur de connexion :", e)
>>>>>>> 3b67d69 (Premier commit du projet via VSCode)
