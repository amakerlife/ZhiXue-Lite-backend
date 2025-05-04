from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def init_db(app):
    db.init_app(app)
    migrate.init_app(app, db)

    # 导入模型以确保它们被 SQLAlchemy 注册
    from app.user.models import User

    with app.app_context():
        db.create_all()