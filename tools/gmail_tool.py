import os
import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from tools.logger import setup_logger
from tools.retry import retry

logger = setup_logger("gmail_tool")


@retry(max_attempts=3, base_delay=2.0, exceptions=(smtplib.SMTPException, OSError))
def send_email(subject: str, html_body: str, to: str | None = None) -> None:
    gmail_from = os.getenv("GMAIL_FROM")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    gmail_to = to or os.getenv("GMAIL_TO")

    if not gmail_password:
        logger.info("GMAIL_APP_PASSWORD not set — skipping email, writing report to .tmp/logs/last-report.html")
        Path(".tmp/logs/last-report.html").write_text(html_body, encoding="utf-8")
        return

    if not all([gmail_from, gmail_to]):
        raise RuntimeError("Set GMAIL_FROM and GMAIL_TO in .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_from
    msg["To"] = gmail_to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_from, gmail_password)
        server.sendmail(gmail_from, gmail_to, msg.as_string())

    logger.info(f"Email sent to {gmail_to}: {subject}")
