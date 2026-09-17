from datetime import datetime
from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    make_response,
    send_file
)
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import re
import secrets

from app import db
from app.models import Organization, Assessment, Question, Response
from questions import QUESTIONS, get_assessment_questions
from recommendations import RECOMMENDATIONS
from category_analysis import calculate_category_analysis
from app.reporting import report_data, text_report, pdf_report, safe_report_filename, send_report_email
from io import BytesIO


main = Blueprint("main", __name__)

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN = re.compile(r"^[0-9+()\-\s]+$")


def normalize_email(value):
    return (value or "").strip().lower()


def registration_error(contact_person, email, phone, password):
    if not EMAIL_PATTERN.fullmatch(email):
        return "Enter a valid email address."
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,148}", contact_person.strip()):
        return "Enter a valid contact-person name."
    phone_digits = re.sub(r"\D", "", phone)
    if not PHONE_PATTERN.fullmatch(phone) or not 7 <= len(phone_digits) <= 15:
        return "Enter a valid phone number including 7 to 15 digits."
    if len(password) < 12 or not all((re.search(r"[a-z]", password), re.search(r"[A-Z]", password), re.search(r"\d", password), re.search(r"[^A-Za-z0-9]", password))):
        return "Use at least 12 characters with uppercase, lowercase, a number, and a symbol."
    return None


def reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")


def current_organization():
    """Return the logged-in organization, clearing a stale session safely."""
    organization_id = session.get("organization_id")
    if not organization_id:
        return None
    organization = db.session.get(Organization, organization_id)
    if not organization:
        session.clear()
    return organization


def assessment_details(assessment):
    """Return category results and prioritized actions for one assessment."""
    question_map = {question["id"]: question for question in QUESTIONS}
    category_responses, recommendations = {}, []
    for response in Response.query.filter_by(assessment_id=assessment.id).all():
        question = question_map.get(response.question_id)
        if question:
            category_responses[response.question_id] = {"category": question["category"], "answer": response.answer}
        if response.answer < 2:
            item = RECOMMENDATIONS.get(response.question_id, {
                "title": f"Strengthen {question['category'] if question else 'this security area'}",
                "recommendation": question["question"] if question else "Review and improve this security control.",
                "priority": "High" if response.answer == 0 else "Medium",
            }).copy()
            item["severity"] = "Critical" if response.answer == 0 else "Needs Improvement"
            recommendations.append(item)
    recommendations.sort(key=lambda item: (item["severity"] != "Critical", item["priority"] != "High"))
    return calculate_category_analysis(category_responses), recommendations


@main.route("/")
def home():
    organization_id = session.get("organization_id")
    organization = None
    if organization_id:
        organization = db.session.get(Organization, organization_id)
    return render_template("index.html", organization=organization)


@main.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        organization_name = request.form.get("organization_name")
        contact_person = request.form.get("contact_person")
        email = normalize_email(request.form.get("email"))
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Check required fields
        if not all([
            organization_name,
            contact_person,
            email,
            phone,
            password,
            confirm_password
        ]):
            flash("Please complete all fields.")
            return redirect(url_for("main.register"))

        # Check password confirmation
        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for("main.register"))

        validation_message = registration_error(contact_person, email, phone, password)
        if validation_message:
            flash(validation_message)
            return redirect(url_for("main.register"))

        # Check duplicate email
        existing_organization = Organization.query.filter_by(
            email=email
        ).first()

        if existing_organization:
            flash("An account with this email already exists.")
            return redirect(url_for("main.register"))

        # Create organization
        organization = Organization(
            organization_name=organization_name,
            contact_person=contact_person,
            email=email,
            phone=phone
        )

        # Hash password
        organization.set_password(password)

        # Save organization
        db.session.add(organization)
        db.session.commit()

        flash("Account created successfully. Please log in.")

        return redirect(url_for("main.login"))

    return render_template("register.html")


@main.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = normalize_email(request.form.get("email"))
        password = request.form.get("password")

        organization = Organization.query.filter_by(
            email=email
        ).first()

        if organization and organization.check_password(password):

            session["organization_id"] = organization.id

            flash("Login successful.")

            return redirect(url_for("main.dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


@main.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        organization = Organization.query.filter_by(email=normalize_email(request.form.get("email"))).first()
        flash("If that email is registered, a password-reset link has been generated.")
        if organization:
            token = reset_serializer().dumps({"organization_id": organization.id})
            reset_url = url_for("main.reset_password", token=token, _external=True)
            # Do not log reset URLs or tokens. This display is intentionally
            # limited to development while email delivery is not configured.
            if current_app.config["ENVIRONMENT"] == "development":
                flash(f"Development reset link: {reset_url}")
        return redirect(url_for("main.login"))
    return render_template("forgot_password.html")


@main.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        organization = db.session.get(Organization, reset_serializer().loads(token, max_age=3600)["organization_id"])
    except (BadSignature, SignatureExpired, KeyError):
        organization = None
    if not organization:
        flash("This password-reset link is invalid or has expired.")
        return redirect(url_for("main.forgot_password"))
    if request.method == "POST":
        password, confirmation = request.form.get("password", ""), request.form.get("confirm_password", "")
        if password != confirmation:
            flash("Passwords do not match.")
        else:
            validation_message = registration_error(organization.contact_person, organization.email, organization.phone, password)
            if validation_message:
                flash(validation_message)
            else:
                organization.set_password(password)
                db.session.commit()
                flash("Your password has been reset. Please log in.")
                return redirect(url_for("main.login"))
    return render_template("reset_password.html")


@main.route("/dashboard")
def dashboard():
    organization = current_organization()
    if not organization:
        flash("Please log in to access your dashboard.")
        return redirect(url_for("main.login"))
    organization_id = organization.id

    # Get the organization's latest assessment
    latest_assessment = Assessment.query.filter_by(
        organization_id=organization_id
    ).order_by(
        Assessment.completed_at.desc()
    ).first()

    assessment_history = Assessment.query.filter_by(
        organization_id=organization_id
    ).order_by(Assessment.completed_at.desc()).limit(10).all()
    category_results, recommendations = assessment_details(latest_assessment) if latest_assessment else ([], [])

    return render_template(
    "dashboard.html",
    organization=organization,
    latest_assessment=latest_assessment,
    recommendations=recommendations,
    category_results=category_results,
    assessment_history=assessment_history
)


@main.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.")

    return redirect(url_for("main.home"))


@main.route("/assessments/<int:assessment_id>/download")
def download_report(assessment_id):
    organization = current_organization()
    if not organization:
        flash("Please log in to download a report.")
        return redirect(url_for("main.login"))
    assessment = Assessment.query.filter_by(id=assessment_id, organization_id=organization.id).first_or_404()
    categories, recommendations = assessment_details(assessment)
    report = pdf_report(report_data(organization, assessment, categories, recommendations))
    return send_file(BytesIO(report), mimetype="application/pdf", as_attachment=True, download_name=safe_report_filename(organization.organization_name))
    lines = [
        "CYBERREADY GHANA — CYBERSECURITY ASSESSMENT REPORT",
        f"Completed: {assessment.completed_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"Score: {int(assessment.score)} / 40",
        f"Risk level: {assessment.risk_level}", "", "CATEGORY ANALYSIS",
    ]
    lines.extend(f"- {item['category']}: {item['score']}/{item['maximum_score']} ({item['percentage']}%), {item['risk_level']}" for item in categories)
    lines.extend(["", "RECOMMENDED ACTIONS"])
    lines.extend(f"- [{item['severity']} / {item['priority']} priority] {item['title']}: {item['recommendation']}" for item in recommendations)
    if not recommendations:
        lines.append("- No immediate weaknesses were identified.")
    response = make_response("\n".join(lines) + "\n")
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename=cyberready-report-{assessment.id}.txt"
    return response

@main.route("/assessments/<int:assessment_id>/download.txt")
def download_text_report(assessment_id):
    organization = current_organization()
    if not organization:
        flash("Please log in to download a report.")
        return redirect(url_for("main.login"))
    assessment = Assessment.query.filter_by(id=assessment_id, organization_id=organization.id).first_or_404()
    categories, recommendations = assessment_details(assessment)
    response = make_response(text_report(report_data(organization, assessment, categories, recommendations)))
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename=cyberready-report-{assessment.id}.txt"
    return response


@main.route("/assessments/<int:assessment_id>/download.pdf")
def download_pdf_report(assessment_id):
    organization = current_organization()
    if not organization:
        flash("Please log in to download a report.")
        return redirect(url_for("main.login"))
    assessment = Assessment.query.filter_by(id=assessment_id, organization_id=organization.id).first_or_404()
    categories, recommendations = assessment_details(assessment)
    report = pdf_report(report_data(organization, assessment, categories, recommendations))
    return send_file(BytesIO(report), mimetype="application/pdf", as_attachment=True, download_name=safe_report_filename(organization.organization_name))


@main.route("/assessments/<int:assessment_id>/email-report", methods=["POST"])
def email_report(assessment_id):
    organization = current_organization()
    if not organization:
        flash("Please log in to email a report.")
        return redirect(url_for("main.login"))
    assessment = Assessment.query.filter_by(id=assessment_id, organization_id=organization.id).first_or_404()
    categories, recommendations = assessment_details(assessment)
    ok, message = send_report_email(organization.email, pdf_report(report_data(organization, assessment, categories, recommendations)))
    flash(message)
    return redirect(url_for("main.dashboard"))


@main.route("/service-worker.js")
def service_worker():
    response = make_response(current_app.send_static_file("service-worker.js"))
    response.headers["Content-Type"] = "application/javascript"
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@main.route("/assessment", methods=["GET", "POST"])
def assessment():
    organization = current_organization()
    if not organization:
        flash("Please log in to take the assessment.")
        return redirect(url_for("main.login"))
    organization_id = organization.id

    if request.method == "POST":
        question_map = {question["id"]: question for question in QUESTIONS}
        selected_ids = session.get("assessment_question_ids", [])
        assessment_questions = [question_map[question_id] for question_id in selected_ids if question_id in question_map]
        if len(assessment_questions) != 20:
            flash("Your assessment session expired. Please start again.")
            return redirect(url_for("main.assessment"))

        answers = {}
        score = 0

        # Calculate the assessment score based on selected questions
        for question in assessment_questions:

            question_id = str(question["id"])
            answer = request.form.get(question_id)

            if answer not in {"yes", "partially", "no"}:
                flash("Please answer every question before submitting.")
                return redirect(url_for("main.assessment"))

            answers[question_id] = answer

            if answer == "yes":
                score += 2

            elif answer == "partially":
                score += 1

            elif answer == "no":
                score += 0

        # Determine risk level
        if score <= 13:
            risk_level = "High Risk"

        elif score <= 26:
            risk_level = "Medium Risk"

        elif score <= 33:
            risk_level = "Good"

        else:
            risk_level = "Strong"

        # Create assessment record
        assessment = Assessment(
            organization_id=organization_id,
            score=score,
            risk_level=risk_level,
            completed_at=datetime.utcnow()
        )

        db.session.add(assessment)

#       Make sure the assessment gets its database ID
        db.session.flush()

        # Save individual responses
        for question in assessment_questions:

            question_id = question["id"]
            answer = answers[str(question_id)]

            # Convert answer to numeric value
            if answer == "yes":
                answer_value = 2

            elif answer == "partially":
                answer_value = 1

            else:
                answer_value = 0

            response = Response(
                assessment_id=assessment.id,
                question_id=question_id,
                answer=answer_value
            )

            db.session.add(response)

        db.session.commit()

        session.pop("assessment_question_ids", None)
        category_results, recommendations = assessment_details(assessment)
        return render_template(
            "assessment_result.html",
            questions=assessment_questions,
            answers=answers,
            score=score,
            risk_level=risk_level,
            category_results=category_results,
            recommendations=recommendations,
            assessment=assessment
        )

    # GET request - generate new random questions for this assessment
    assessment_questions = get_assessment_questions()
    session["assessment_question_ids"] = [question["id"] for question in assessment_questions]
    session["assessment_draft_id"] = secrets.token_urlsafe(16)
    
    return render_template(
        "assessment.html",
        questions=assessment_questions,
        draft_id=session["assessment_draft_id"]
    )
