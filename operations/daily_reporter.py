"""
Agent 6: Daily Reporter
Compiles everything and sends a morning digest email.

Usage:
    python -m operations.daily_reporter
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date
from dotenv import load_dotenv
from tools.sheets_api import read_all, TABS
from tools.gmail_tool import send_email
from tools.logger import setup_logger

load_dotenv()
logger = setup_logger("daily_reporter")

SCRIPTS_DIR = Path(".tmp/scripts")
THUMBNAILS_DIR = Path(".tmp/thumbnails")


def _todays_outliers() -> list[dict]:
    rows = read_all(TABS["outliers"])
    today = str(date.today())
    result = []
    for row in rows[1:]:
        if row and row[0] == today and len(row) >= 7:
            try:
                score = float(row[5])
            except (ValueError, IndexError):
                score = 0.0
            result.append(
                {
                    "channel": row[2] if len(row) > 2 else "",
                    "title": row[3] if len(row) > 3 else "",
                    "views": row[4] if len(row) > 4 else "0",
                    "score": row[5] if len(row) > 5 else "0",
                    "url": row[6] if len(row) > 6 else "#",
                    "_score": score,
                }
            )
    return sorted(result, key=lambda x: x["_score"], reverse=True)[:5]


def _calendar_entry() -> dict | None:
    rows = read_all(TABS["calendar"])
    today = str(date.today())
    for row in rows[1:]:
        if row and row[0] == today and len(row) >= 4:
            return {
                "title": row[1] if len(row) > 1 else "TBD",
                "hook": row[2] if len(row) > 2 else "TBD",
                "script_status": row[3] if len(row) > 3 else "Pending",
                "thumbnail_status": row[4] if len(row) > 4 else "Pending",
            }
    return None


def _script_preview() -> str:
    today = str(date.today())
    path = SCRIPTS_DIR / f"{today}-script.md"
    if not path.exists():
        return "Script not yet generated — run Script Writer."
    content = path.read_text(encoding="utf-8")
    # Skip frontmatter, show first chunk of actual script
    parts = content.split("---\n\n")
    body = parts[-1] if len(parts) > 1 else content
    preview = body[:700]
    return (preview + "...") if len(body) > 700 else preview


def _thumbnail_count() -> int:
    today = str(date.today())
    return len(list(THUMBNAILS_DIR.glob(f"{today}-thumbnail-*.png")))


def _build_html(outliers: list, cal: dict | None, preview: str, thumb_count: int) -> str:
    today = str(date.today())

    video_block = ""
    if cal:
        video_block = f"""
<div style="background:#F0FDF4;border-left:4px solid #059669;padding:16px;margin:20px 0;border-radius:6px;">
  <h2 style="margin:0 0 10px;color:#065F46;font-size:16px;">TODAY'S VIDEO</h2>
  <p style="margin:4px 0;"><strong>Title:</strong> {cal['title']}</p>
  <p style="margin:4px 0;"><strong>Hook:</strong> <em>{cal['hook']}</em></p>
  <p style="margin:4px 0;"><strong>Script:</strong> {cal['script_status']} &nbsp;|&nbsp; <strong>Thumbnails:</strong> {thumb_count} ready</p>
</div>"""

    outlier_rows = "".join(
        f"""<tr>
          <td style="padding:8px;border-bottom:1px solid #E5E7EB;">
            <a href="{o['url']}" style="color:#4F46E5;text-decoration:none;">{o['title'][:65]}</a>
          </td>
          <td style="padding:8px;border-bottom:1px solid #E5E7EB;color:#6B7280;font-size:13px;">{o['channel']}</td>
          <td style="padding:8px;border-bottom:1px solid #E5E7EB;font-weight:bold;color:#059669;">{o['score']}x</td>
        </tr>"""
        for o in outliers
    )

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#111;background:#fff;">
  <h1 style="font-size:22px;margin-bottom:4px;">Content Machine</h1>
  <p style="color:#9CA3AF;margin-top:0;font-size:14px;">{today}</p>

  {video_block}

  <h2 style="font-size:15px;color:#1F2937;border-bottom:2px solid #E5E7EB;padding-bottom:6px;">Script Preview</h2>
  <div style="background:#F9FAFB;padding:14px;border-radius:8px;font-size:13px;line-height:1.7;white-space:pre-wrap;font-family:monospace;">{preview}</div>

  <h2 style="font-size:15px;color:#1F2937;border-bottom:2px solid #E5E7EB;padding-bottom:6px;margin-top:24px;">Top Outliers Today</h2>
  {"<table style='width:100%;border-collapse:collapse;font-size:13px;'><thead><tr style='background:#F3F4F6;'><th style='padding:8px;text-align:left;'>Title</th><th style='padding:8px;text-align:left;'>Channel</th><th style='padding:8px;text-align:left;'>Score</th></tr></thead><tbody>" + outlier_rows + "</tbody></table>" if outlier_rows else "<p style='color:#9CA3AF;'>No outliers found today.</p>"}

  <p style="font-size:12px;color:#D1D5DB;margin-top:32px;border-top:1px solid #F3F4F6;padding-top:12px;">
    Content Machine &mdash; automated with Claude Code
  </p>
</body>
</html>"""


def run():
    logger.info("=== Daily Reporter starting ===")

    today = str(date.today())
    outliers = _todays_outliers()
    cal = _calendar_entry()
    preview = _script_preview()
    thumb_count = _thumbnail_count()

    html = _build_html(outliers, cal, preview, thumb_count)

    subject = f"Content Machine — {today}"
    if cal and cal.get("title") and cal["title"] != "TBD":
        subject += f" | {cal['title'][:45]}"

    try:
        send_email(subject, html)
        logger.info("Daily report email sent")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

    logger.info("=== Daily Reporter complete ===")


if __name__ == "__main__":
    run()
