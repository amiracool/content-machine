import os
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from tools.retry import retry
from tools.logger import setup_logger

logger = setup_logger("sheets_api")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS_FILE = Path("credentials.json")

TABS = {
    "outliers": "Daily Outliers",
    "calendar": "Content Calendar",
    "brand_voice": "Brand Voice",
    "competitors": "Competitor Tracker",
}

HEADERS = {
    "outliers": [
        "Date", "Platform", "Channel", "Title",
        "Views", "Outlier Score", "URL", "Hook Transcript",
    ],
    "calendar": [
        "Date", "Your Title", "Hook", "Script Status",
        "Thumbnail Status", "Publish Status",
    ],
    "brand_voice": ["Key", "Value"],
    "competitors": [
        "Channel", "Subscribers", "Avg Views", "Niche", "YouTube URL",
    ],
}


def _sheet_id() -> str:
    sid = os.getenv("GOOGLE_SHEET_ID", "")
    if not sid:
        raise RuntimeError("GOOGLE_SHEET_ID not set in environment")
    return sid


def _client():
    if not CREDS_FILE.exists():
        raise FileNotFoundError(
            f"credentials.json not found at {CREDS_FILE.resolve()}. "
            "Download it from Google Cloud Console."
        )
    creds = Credentials.from_service_account_file(str(CREDS_FILE), scopes=SCOPES)
    return build("sheets", "v4", credentials=creds).spreadsheets()


@retry(max_attempts=3)
def append_rows(tab: str, rows: list[list]) -> None:
    _client().values().append(
        spreadsheetId=_sheet_id(),
        range=f"{tab}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()
    logger.info(f"Appended {len(rows)} rows to '{tab}'")


@retry(max_attempts=3)
def read_all(tab: str) -> list[list]:
    resp = (
        _client()
        .values()
        .get(spreadsheetId=_sheet_id(), range=f"{tab}!A:Z")
        .execute()
    )
    return resp.get("values", [])


@retry(max_attempts=3)
def write_range(tab: str, cell_range: str, values: list[list]) -> None:
    _client().values().update(
        spreadsheetId=_sheet_id(),
        range=f"{tab}!{cell_range}",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()
    logger.debug(f"Wrote to {tab}!{cell_range}")


def read_brand_voice() -> dict:
    rows = read_all(TABS["brand_voice"])
    return {
        row[0]: row[1]
        for row in rows[1:]
        if len(row) >= 2 and row[0] and row[1]
    }


def read_competitors() -> list[dict]:
    rows = read_all(TABS["competitors"])
    if len(rows) < 2:
        return []
    headers = rows[0]
    return [
        dict(zip(headers, row))
        for row in rows[1:]
        if row
    ]
