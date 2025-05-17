from datetime import datetime

from flask_login import UserMixin
from app.database import db
from werkzeug.security import generate_password_hash, check_password_hash


class ZhiXueUser(db.Model):
    __tablename__ = "zhixue_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    cookie = db.Column(db.Text, nullable=True)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, index=True)
    password_hash = db.Column(db.String(200))
    role = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    registration_ip = db.Column(db.String(45), nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)
    zhixue_account_id = db.Column(db.Integer, db.ForeignKey("zhixue_users.id"), nullable=True)

    zhixue = db.relationship("ZhiXueUser", backref="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "zhixue_username": self.zhixue.username if self.zhixue else None,
        }
