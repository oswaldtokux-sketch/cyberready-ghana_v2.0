import os

import pytest

from app import create_app, db
from app.models import Assessment, Organization, Response
from app.reporting import pdf_report, report_data, send_report_email


@pytest.fixture()
def app():
    application = create_app({
        "TESTING": True, "SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with application.app_context():
        db.drop_all()
        db.create_all()
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="team@example.com"):
    return client.post("/register", data={
        "organization_name": "Example Ltd", "contact_person": "Ama Mensah",
        "email": email, "phone": "+233 24 123 4567",
        "password": "SecurePassword!1", "confirm_password": "SecurePassword!1",
    }, follow_redirects=True)


def login(client, email="team@example.com"):
    return client.post("/login", data={"email": email, "password": "SecurePassword!1"}, follow_redirects=True)


def test_application_starts(app):
    assert app.url_map.bind("localhost")


def test_registration_and_normalized_duplicate_email(client):
    assert b"Account created successfully" in register(client, "Team@Example.COM").data
    assert b"already exists" in register(client, " team@example.com ").data


def test_login_works(client):
    register(client)
    assert b"Example Ltd" in login(client).data


def test_csrf_is_active():
    app = create_app({"TESTING": True, "SECRET_KEY": "csrf-test", "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    response = app.test_client().post("/login", data={"email": "a@example.com", "password": "x"})
    assert response.status_code == 400


def test_assessment_uses_the_displayed_questions_for_scoring(client, app):
    register(client)
    login(client)
    client.get("/assessment")
    with client.session_transaction() as state:
        selected = state["assessment_question_ids"]
    response = client.post("/assessment", data={str(question_id): "yes" for question_id in selected}, follow_redirects=True)
    assert b"40 / 40" in response.data
    with app.app_context():
        assessment = Assessment.query.one()
        responses = Response.query.filter_by(assessment_id=assessment.id).all()
        assert {item.question_id for item in responses} == set(selected)
        assert assessment.score == 40


def test_organization_cannot_access_another_report(client, app):
    register(client, "one@example.com")
    login(client, "one@example.com")
    client.get("/assessment")
    with client.session_transaction() as state:
        selected = state["assessment_question_ids"]
    client.post("/assessment", data={str(question_id): "yes" for question_id in selected})
    with app.app_context():
        assessment_id = Assessment.query.one().id
    client.get("/logout")
    register(client, "two@example.com")
    login(client, "two@example.com")
    assert client.get(f"/assessments/{assessment_id}/download.pdf").status_code == 404


def test_pdf_generation_and_unconfigured_email(app, monkeypatch):
    with app.app_context():
        organization = Organization(organization_name="Example", contact_person="Ama Mensah", email="team@example.com", phone="1234567")
        organization.set_password("SecurePassword!1")
        assessment = Assessment(score=40, risk_level="Strong", completed_at=__import__("datetime").datetime.utcnow())
        data = report_data(organization, assessment, [], [])
    assert pdf_report(data).startswith(b"%PDF")
    monkeypatch.delenv("CYBERREADY_EMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("CYBERREADY_EMAIL_APP_PASSWORD", raising=False)
    assert send_report_email("team@example.com", b"pdf")[0] is False


def test_static_offline_assets_are_available(client):
    assert client.get("/service-worker.js").status_code == 200
    assert client.get("/static/manifest.webmanifest").status_code == 200
    assert client.get("/static/js/assessment-draft.js").status_code == 200
