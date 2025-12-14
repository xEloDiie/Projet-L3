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
