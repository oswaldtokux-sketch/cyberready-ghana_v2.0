from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from app import db
from app.models import Organization, Assessment, Question, Response
from questions import QUESTIONS
from recommendations import RECOMMENDATIONS
from category_analysis import calculate_category_analysis


main = Blueprint("main", __name__)


@main.route("/")
def home():
    return render_template("index.html")


@main.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        organization_name = request.form.get("organization_name")
        contact_person = request.form.get("contact_person")
        email = request.form.get("email")
        phone = request.form.get("phone")
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

        email = request.form.get("email")
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


@main.route("/dashboard")
def dashboard():

    organization_id = session.get("organization_id")

    if not organization_id:
        flash("Please log in to access your dashboard.")
        return redirect(url_for("main.login"))

    organization = db.session.get(
        Organization,
        organization_id
    )

    if not organization:
        session.clear()
        flash("Account not found. Please log in again.")
        return redirect(url_for("main.login"))

    # Get the organization's latest assessment
    latest_assessment = Assessment.query.filter_by(
        organization_id=organization_id
    ).order_by(
        Assessment.completed_at.desc()
    ).first()

    recommendations = []
    category_results = []

    if latest_assessment:

        responses = Response.query.filter_by(
            assessment_id=latest_assessment.id
        ).all()

        # Prepare responses for category analysis
        category_responses = {}

        for response in responses:

            question = next(
                (
                    q for q in QUESTIONS
                    if q["id"] == response.question_id
                ),
                None
            )

            if question:

                category_responses[response.question_id] = {
                    "category": question["category"],
                    "answer": response.answer
                }

            # Generate recommendations
            if response.answer < 2:

                recommendation = RECOMMENDATIONS.get(
                    response.question_id
                )

                if recommendation:

                    item = recommendation.copy()

                    if response.answer == 0:
                        item["severity"] = "Critical"

                    else:
                        item["severity"] = "Needs Improvement"

                    item["question_id"] = response.question_id

                    recommendations.append(item)

        # Calculate category-level results
        category_results = calculate_category_analysis(
            category_responses
        )

    # Sort recommendations by severity and priority
    recommendations.sort(
        key=lambda item: (
            0 if item["severity"] == "Critical" else 1,
            0 if item["priority"] == "High" else 1
        )
    )

    return render_template(
    "dashboard.html",
    organization=organization,
    latest_assessment=latest_assessment,
    recommendations=recommendations,
    category_results=category_results
)


@main.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.")

    return redirect(url_for("main.login"))

@main.route("/assessment", methods=["GET", "POST"])
def assessment():

    organization_id = session.get("organization_id")

    if not organization_id:
        flash("Please log in to take the assessment.")
        return redirect(url_for("main.login"))

    if request.method == "POST":

        answers = {}
        score = 0

        # Calculate the assessment score
        for question in QUESTIONS:

            question_id = str(question["id"])
            answer = request.form.get(question_id)

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
        for question in QUESTIONS:

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

        return render_template(
            "assessment_result.html",
            questions=QUESTIONS,
            answers=answers,
            score=score,
            risk_level=risk_level
        )

    return render_template(
        "assessment.html",
        questions=QUESTIONS
    )