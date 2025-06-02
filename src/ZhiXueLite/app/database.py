from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase


class BaseDb(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=BaseDb)
migrate = Migrate()


def init_db(app):
    db.init_app(app)
    migrate.init_app(app, db)    # 导入模型以确保它们被 SQLAlchemy 注册
    from app.user.models import User
    from app.exam.models import Student, Exam, Subject, Score

    with app.app_context():
        db.create_all()
