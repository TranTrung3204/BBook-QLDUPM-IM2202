import os
import json
import cloudinary
from flask import Flask
from flask_dance.contrib.google import make_google_blueprint
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import quote

# Cho phép chạy HTTP khi dev
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Load secrets từ env hoặc secret.json
BASE_DIR = os.path.dirname(__file__)
secrets = {}
secret_file = os.path.join(BASE_DIR, "data", "secret.json")
if os.path.exists(secret_file):
    try:
        with open(secret_file, "r", encoding="utf-8") as f:
            secrets = json.load(f)
    except Exception:
        secrets = {}

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.get("FLASK_SECRET_KEY") or "dev-secret-key"

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "SQLALCHEMY_DATABASE_URI",
    "mysql+pymysql://root:%s@localhost/bbookqldapm?charset=utf8mb4" % quote('Admin@123')
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400

cloudinary.config(
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME") or secrets.get("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.environ.get("CLOUDINARY_API_KEY") or secrets.get("CLOUDINARY_API_KEY"),
    api_secret = os.environ.get("CLOUDINARY_API_SECRET") or secrets.get("CLOUDINARY_API_SECRET")
)

google_bp = make_google_blueprint(
    client_id=os.environ.get("GOOGLE_CLIENT_ID") or secrets.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET") or secrets.get("GOOGLE_CLIENT_SECRET"),
    scope=["openid", "https://www.googleapis.com/auth/userinfo.profile",
           "https://www.googleapis.com/auth/userinfo.email"]
)

app.register_blueprint(google_bp, url_prefix="/login")

db = SQLAlchemy(app=app)
