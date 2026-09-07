from app import create_app, db
from app.models import Question
from questions import QUESTIONS


app = create_app()

with app.app_context():

    for question_data in QUESTIONS:

        existing_question = Question.query.get(
            question_data["id"]
        )

        if existing_question:
            continue

        question = Question(
            id=question_data["id"],
            category=question_data["category"],
            question_text=question_data["question"],
            weight=1.0
        )

        db.session.add(question)

    db.session.commit()

    print("20 cybersecurity questions added successfully.")