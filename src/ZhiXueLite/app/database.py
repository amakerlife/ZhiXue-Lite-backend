from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase


class BaseDBClass(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=BaseDBClass)
migrate = Migrate()


def init_db(app):
    db.init_app(app)
    migrate.init_app(app, db)
