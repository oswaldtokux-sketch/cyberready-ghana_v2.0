from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
import os
import secrets


db = SQLAlchemy()
csrf = CSRFProtect()


def create_app(test_config=None):

    app = Flask(__name__)

    environment = os.environ.get("CYBERREADY_ENV", os.environ.get("FLASK_ENV", "development")).lower()
    secret_key = os.environ.get("SECRET_KEY")
    if environment == "production" and not secret_key:
        raise RuntimeError("SECRET_KEY must be set when CYBERREADY_ENV=production.")
    app.config.update(
        SECRET_KEY=secret_key or secrets.token_urlsafe(32),
        ENVIRONMENT=environment,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=environment == "production",
    )
    if test_config:
        app.config.update(test_config)

    # Database configuration
    basedir = os.path.abspath(os.path.dirname(__file__))

    database_dir = os.path.abspath(
        os.path.join(
            basedir,
            "..",
            "database"
        )
    )

    # Create database directory if it does not exist
    os.makedirs(database_dir, exist_ok=True)

    database_path = os.path.join(
        database_dir,
        "cyberready.db"
    )

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + database_path

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    csrf.init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    from app.models import Organization

    with app.app_context():
        db.create_all()

    return app
