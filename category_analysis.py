CATEGORIES = [
    "Passwords & Account Security",
    "Data Protection",
    "Devices & Software",
    "Phishing & Staff Awareness",
    "Incident Response & Business Continuity"
]


def calculate_category_analysis(responses):
    """
    Calculate cybersecurity performance for each category.

    responses should contain:
    {
        question_id: {
            "category": "...",
            "answer": 0, 1, or 2
        }
    }
    """

    results = []

    for category in CATEGORIES:

        category_responses = [
            response
            for response in responses.values()
            if response["category"] == category
        ]

        if not category_responses:
            continue

        total_score = sum(
            response["answer"]
            for response in category_responses
        )

        maximum_score = len(category_responses) * 2

        percentage = (
            total_score / maximum_score
        ) * 100

        if percentage < 40:
            risk_level = "High Risk"

        elif percentage < 70:
            risk_level = "Medium Risk"

        elif percentage < 85:
            risk_level = "Good"

        else:
            risk_level = "Strong"

        results.append({
            "category": category,
            "score": total_score,
            "maximum_score": maximum_score,
            "percentage": round(percentage),
            "risk_level": risk_level
        })

    return results