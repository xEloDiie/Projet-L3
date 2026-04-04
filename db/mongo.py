import os
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Charger le .env
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# Créer client et DB
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
db = client["404HackNotFound"]

# Collections
users_collection = db["users"]
roles_collection = db["roles"]
challenges_collection = db["challenges"]
users_progression_collection = db["users_progression"]
logs_collection = db["logs"]

# Vérification de la connexion
try:
    client.admin.command('ping')
    print("Connexion à MongoDB réussie.")
except Exception as e:
    print("Erreur de connexion :", e)