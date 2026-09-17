"""Shared text, PDF, and email reporting helpers."""
from email.message import EmailMessage
from io import BytesIO
import os, re, smtplib
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BRAND = colors.HexColor("#0F5C46")
INK = colors.HexColor("#173042")
MUTED = colors.HexColor("#5E7180")
PALE_GREEN = colors.HexColor("#E6F3EE")
PALE_BLUE = colors.HexColor("#EDF4F8")
PALE_RED = colors.HexColor("#FCEBE8")


def report_data(organization, assessment, categories, recommendations):
    return {"organization": organization.organization_name, "contact_person": organization.contact_person, "email": organization.email, "phone": organization.phone, "completed": assessment.completed_at.strftime("%Y-%m-%d %H:%M UTC"), "score": int(assessment.score), "risk_level": assessment.risk_level, "categories": categories, "recommendations": recommendations}


def safe_report_filename(organization_name):
    name = re.sub(r"[^A-Za-z0-9]+", "_", organization_name or "Organization").strip("_")
    return f"CyberReady_{name[:80] or 'Organization'}_Report.pdf"


def text_report(data):
    lines = ["CYBERREADY GHANA - CYBERSECURITY ASSESSMENT REPORT", f"Organization: {data['organization']}", f"Completed: {data['completed']}", f"Score: {data['score']} / 40", f"Risk level: {data['risk_level']}", "", "CATEGORY ANALYSIS"]
    lines.extend(f"- {item['category']}: {item['score']}/{item['maximum_score']} ({item['percentage']}%), {item['risk_level']}" for item in data["categories"])
    lines.extend(["", "RECOMMENDED ACTIONS"])
    lines.extend(f"- [{item['severity']} / {item['priority']} priority] {item['title']}: {item['recommendation']}" for item in data["recommendations"])
    if not data["recommendations"]:
        lines.append("- No immediate weaknesses were identified. Continue reviewing your controls regularly.")
    return "\n".join(lines) + "\n"


def _styles():
    base = getSampleStyleSheet()
    return {
        "cover_brand": ParagraphStyle("CoverBrand", parent=base["Title"], fontName="Helvetica-Bold", fontSize=25, leading=30, textColor=BRAND, alignment=TA_CENTER, spaceAfter=12),
        "cover_title": ParagraphStyle("CoverTitle", parent=base["Title"], fontName="Helvetica", fontSize=18, leading=24, textColor=INK, alignment=TA_CENTER),
        "cover_detail": ParagraphStyle("CoverDetail", parent=base["BodyText"], fontSize=11, leading=17, textColor=INK, alignment=TA_CENTER),
        "heading": ParagraphStyle("ReportHeading", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=16, leading=21, textColor=BRAND, spaceBefore=4, spaceAfter=10),
        "subheading": ParagraphStyle("ReportSubheading", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=INK, spaceAfter=4),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontSize=9.5, leading=14, textColor=INK),
        "small": ParagraphStyle("ReportSmall", parent=base["BodyText"], fontSize=8, leading=10, textColor=MUTED),
        "score": ParagraphStyle("Score", parent=base["Title"], fontName="Helvetica-Bold", fontSize=30, leading=34, textColor=BRAND, alignment=TA_CENTER),
        "table": ParagraphStyle("Table", parent=base["BodyText"], fontSize=8.5, leading=11, textColor=INK),
        "table_header": ParagraphStyle("TableHeader", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8.5, leading=10, textColor=colors.white),
    }


def _footer(canvas, document):
    canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#D5E0E5")); canvas.line(document.leftMargin, 14 * mm, A4[0] - document.rightMargin, 14 * mm)
    canvas.setFillColor(MUTED); canvas.setFont("Helvetica", 8); canvas.drawString(document.leftMargin, 9 * mm, "CyberReady Ghana | Cybersecurity Assessment Report"); canvas.drawRightString(A4[0] - document.rightMargin, 9 * mm, f"Page {document.page}"); canvas.restoreState()


def _risk_color(risk_level):
    return {"High Risk": colors.HexColor("#B42318"), "Medium Risk": colors.HexColor("#A15C00"), "Good": colors.HexColor("#176B4D"), "Strong": BRAND}.get(risk_level, INK)


def _score_bar(percentage, width=72 * mm):
    value = max(0, min(100, int(percentage))); filled = width * value / 100
    bar = Table([["", ""]], colWidths=[filled, width - filled], rowHeights=[5 * mm])
    bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), BRAND), ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#E3EBEF")), ("BOX", (0, 0), (-1, -1), 0, colors.white)]))
    return bar


def pdf_report(data):
    """Render a print-friendly, multi-page report from existing results only."""
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=19 * mm, rightMargin=19 * mm, topMargin=19 * mm, bottomMargin=22 * mm, title="CyberReady Ghana Assessment Report")
    styles = _styles(); percentage = round((data["score"] / 40) * 100); categories = data["categories"]
    stronger = [item["category"] for item in categories if item["risk_level"] in {"Good", "Strong"}]
    weaker = [item["category"] for item in categories if item["risk_level"] in {"High Risk", "Medium Risk"}]
    story = [Spacer(1, 49 * mm), Paragraph("CYBERREADY GHANA", styles["cover_brand"]), Paragraph("Cybersecurity Assessment Report", styles["cover_title"]), Spacer(1, 19 * mm)]
    cover_rows = [[Paragraph("<b>Organization</b>", styles["small"]), Paragraph(escape(data["organization"]), styles["cover_detail"])], [Paragraph("<b>Assessment completion date</b>", styles["small"]), Paragraph(escape(data["completed"]), styles["cover_detail"])], [Paragraph("<b>Overall score</b>", styles["small"]), Paragraph(f"{data['score']} / 40 ({percentage}%)", styles["cover_detail"])], [Paragraph("<b>Overall risk level</b>", styles["small"]), Paragraph(escape(data["risk_level"]), styles["cover_detail"])]]
    cover = Table(cover_rows, colWidths=[61 * mm, 91 * mm], hAlign="CENTER")
    cover.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE_GREEN), ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#C8DED4")), ("INNERGRID", (0, 0), (-1, -1), .25, colors.HexColor("#C8DED4")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story += [cover, Spacer(1, 12 * mm), Paragraph("Prepared using your completed CyberReady Ghana cybersecurity assessment.", styles["cover_detail"]), PageBreak(), Paragraph("Executive Summary", styles["heading"])]
    summary = f"This assessment recorded an overall score of <b>{data['score']} out of 40 ({percentage}%)</b>, classified as <b>{escape(data['risk_level'])}</b>."
    if stronger: summary += " Stronger results were recorded in " + escape(", ".join(stronger)) + "."
    if weaker: summary += " The categories needing the most attention are " + escape(", ".join(weaker)) + "."
    if not stronger and not weaker: summary += " Category results are shown in the analysis below."
    story += [Paragraph(summary, styles["body"]), Spacer(1, 10), Paragraph("Overall Assessment", styles["heading"])]
    overview = Table([[Paragraph(f"{data['score']} / 40", styles["score"]), Paragraph(f"<b>{percentage}%</b><br/><font color=\"{_risk_color(data['risk_level']).hexval()}\">{escape(data['risk_level'])}</font>", styles["cover_detail"])]], colWidths=[76 * mm, 76 * mm])
    overview.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE), ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#D5E0E5")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]))
    story += [overview, Spacer(1, 5), _score_bar(percentage), Spacer(1, 13), Paragraph("Category Analysis", styles["heading"])]
    rows = [[Paragraph("Category", styles["table_header"]), Paragraph("Score", styles["table_header"]), Paragraph("Percentage", styles["table_header"]), Paragraph("Risk / status", styles["table_header"]), Paragraph("Progress", styles["table_header"])]]
    for item in categories:
        rows.append([Paragraph(escape(item["category"]), styles["table"]), Paragraph(f"{item['score']} / {item['maximum_score']}", styles["table"]), Paragraph(f"{item['percentage']}%", styles["table"]), Paragraph(f"<font color=\"{_risk_color(item['risk_level']).hexval()}\"><b>{escape(item['risk_level'])}</b></font>", styles["table"]), _score_bar(item["percentage"], 37 * mm)])
    analysis = Table(rows, colWidths=[50 * mm, 20 * mm, 22 * mm, 29 * mm, 37 * mm], repeatRows=1)
    analysis.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BRAND), ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#D5E0E5")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFB")]), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [analysis, PageBreak(), Paragraph("Recommended Actions", styles["heading"])]
    if data["recommendations"]:
        for priority in ("High", "Medium"):
            items = [item for item in data["recommendations"] if item.get("priority") == priority]
            if items: story += [Paragraph(f"{priority}-priority actions", styles["subheading"])]
            for item in items:
                badge = f"<b>{escape(item.get('severity', 'Needs Improvement'))}</b> | {escape(priority)} priority"
                card = Table([[Paragraph(badge, styles["small"])], [Paragraph(escape(item["title"]), styles["subheading"])], [Paragraph(escape(item["recommendation"]), styles["body"])]], colWidths=[158 * mm])
                card.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), PALE_RED if item.get("severity") == "Critical" else PALE_BLUE), ("BACKGROUND", (0, 1), (-1, -1), colors.white), ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#D5E0E5")), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
                story += [KeepTogether([card, Spacer(1, 7)])]
    else: story += [Paragraph("No immediate weaknesses were identified from the submitted responses. Continue reviewing and testing controls regularly.", styles["body"])]
    methodology = "The assessment contains 20 questions: four selected from each of the application’s five cybersecurity categories. Each answer is scored using the existing CyberReady Ghana scale: <b>Yes = 2</b>, <b>Partially = 1</b>, and <b>No = 0</b>. The overall score is out of 40. Category scores and the risk/status labels in this report are calculated from the answers recorded for this completed assessment."
    story += [PageBreak(), Paragraph("Methodology", styles["heading"]), Paragraph(methodology, styles["body"])]
    document.build(story, onFirstPage=lambda canvas, doc: None, onLaterPages=_footer)
    return buffer.getvalue()


def send_report_email(recipient, pdf_bytes):
    sender = os.environ.get("CYBERREADY_EMAIL_ADDRESS"); password = os.environ.get("CYBERREADY_EMAIL_APP_PASSWORD")
    if not sender or not password: return False, "Email reporting is not currently configured. Please download the PDF report instead."
    message = EmailMessage(); message["Subject"] = "CyberReady Ghana Assessment Report"; message["From"] = sender; message["To"] = recipient
    message.set_content("Your CyberReady Ghana cybersecurity assessment report is attached. Please review the recommendations and suggested actions with your team.")
    message.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename="cyberready-ghana-assessment-report.pdf")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp: smtp.login(sender, password); smtp.send_message(message)
    except (OSError, smtplib.SMTPException): return False, "We could not send the report email right now. Please download the PDF report instead."
    return True, "Your assessment report has been emailed to your registered address."
