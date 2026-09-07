from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os


db = SQLAlchemy()


def create_app():

    app = Flask(__name__)

    app.config["SECRET_KEY"] = "cyberready-development-key"

    # Database configuration
    basedir = os.path.abspath(os.path.dirname(__file__))

    database_path = os.path.join(
        basedir,
        "..",
        "database",
        "cyberready.db"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///" + os.path.abspath(database_path)
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    from app.models import Organization

    with app.app_context():
        db.create_all()

    return app