import os
import json
import cloudinary
from flask import Flask
from flask_dance.contrib.google import make_google_blueprint
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import quote

# Cho phép chạy HTTP khi dev
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
#
# Load secret.json
BASE_DIR = os.path.dirname(__file__)
secret_file = os.path.join(BASE_DIR, "data", "secret.json")
with open(secret_file, "r", encoding="utf-8") as f: secrets = json.load(f)


app = Flask(__name__)
app.secret_key = '^&*)%T*O&T*^&%)*^T%*&T)*O&RTO)(*FGKYTDFHKTFGK'
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:%s@localhost/bbook_qldapm?charset=utf8mb4" % quote('Admin@123')


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400

cloudinary.config(cloud_name=secrets["CLOUDINARY_CLOUD_NAME"],
                  api_key=secrets["CLOUDINARY_API_KEY"],
                  api_secret=secrets["CLOUDINARY_API_SECRET"])
# Google OAuth config
google_bp = make_google_blueprint(
    client_id=secrets["GOOGLE_CLIENT_ID"],
    client_secret=secrets["GOOGLE_CLIENT_SECRET"],
    scope=["openid", "https://www.googleapis.com/auth/userinfo.profile",
                    "https://www.googleapis.com/auth/userinfo.email", ])

app.register_blueprint(google_bp, url_prefix="/login")

db = SQLAlchemy(app=app)
#123