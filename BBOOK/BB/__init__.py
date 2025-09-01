import cloudinary
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import quote

app = Flask(__name__)
app.secret_key = '^&*)%T*O&T*^&%)*^T%*&T)*O&RTO)(*FGKYTDFHKTFGK'
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:%s@localhost/bbook_qldapm?charset=utf8mb4" % quote ('Admin@123')
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True

cloudinary.config(
    cloud_name = 'dcxqcrv7r',
    api_key =  '891277327691127',
    api_secret =  'Tb5b-XfyDYroTE0jsuoo-LyjyFQ',
)

db = SQLAlchemy(app=app)
login = LoginManager(app=app)