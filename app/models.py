from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


class Organization(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    organization_name = db.Column(
        db.String(150),
        nullable=False
    )

    contact_person = db.Column(
        db.String(150),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    phone = db.Column(
        db.String(30),
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )


class Assessment(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organization.id"),
        nullable=False
    )

    score = db.Column(
        db.Float,
        nullable=True
    )

    risk_level = db.Column(
        db.String(30),
        nullable=True
    )

    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class Question(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    category = db.Column(
        db.String(100),
        nullable=False
    )

    question_text = db.Column(
        db.Text,
        nullable=False
    )

    weight = db.Column(
        db.Float,
        default=1.0
    )


class Response(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    assessment_id = db.Column(
        db.Integer,
        db.ForeignKey("assessment.id"),
        nullable=False
    )

    question_id = db.Column(
        db.Integer,
        db.ForeignKey("question.id"),
        nullable=False
    )

    answer = db.Column(
        db.Integer,
        nullable=False
    )    