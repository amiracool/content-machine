"""
One-time setup: initializes the Google Sheet with all 4 tabs and headers.

Run this before anything else:
    python setup_sheets.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

TABS = {
    "Daily Outliers": [
        "Date", "Platform", "Channel", "Title",
        "Views", "Outlier Score", "URL", "Hook Transcript",
    ],
    "Content Calendar": [
        "Date", "Your Title", "Hook", "Script Status",
        "Thumbnail Status", "Publish Status",
    ],
    "Brand Voice": ["Key", "Value"],
    "Competitor Tracker": [
        "Channel", "Subscribers", "Avg Views", "Niche", "YouTube URL",
    ],
}

BRAND_VOICE_SEED = [
    ["Tone", ""],
    ["ICA", ""],
    ["Topics", ""],
    ["Hooks That Work", ""],
    ["Words You Use", ""],
    ["Words You Avoid", ""],
    ["Title Patterns", ""],
    ["Thumbnail Style", ""],
]


def main():
    creds_file = Path("credentials.json")
    if not creds_file.exists():
        print("ERROR: credentials.json not found.")
        print("Download it from Google Cloud Console > Service Accounts > Keys.")
        sys.exit(1)

    sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEET_ID not set in .env")
        sys.exit(1)

    creds = Credentials.from_service_account_file(str(creds_file), scopes=SCOPES)
    svc = build("sheets", "v4", credentials=creds).spreadsheets()

    # Get existing sheets
    meta = svc.get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in meta["sheets"]}
    print(f"Existing tabs: {existing}")

    requests = []

    # Add missing tabs
    for tab_name in TABS:
        if tab_name not in existing:
            requests.append(
                {"addSheet": {"properties": {"title": tab_name}}}
            )
            print(f"  Will create tab: {tab_name}")

    if requests:
        svc.batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": requests},
        ).execute()
        print("Tabs created.")

    # Write headers
    for tab_name, headers in TABS.items():
        svc.values().update(
            spreadsheetId=sheet_id,
            range=f"{tab_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [headers]},
        ).execute()
        print(f"  Headers set: {tab_name}")

    # Seed Brand Voice keys
    svc.values().update(
        spreadsheetId=sheet_id,
        range="Brand Voice!A2",
        valueInputOption="USER_ENTERED",
        body={"values": BRAND_VOICE_SEED},
    ).execute()
    print("  Brand Voice keys seeded (fill in the Value column)")

    print("\nSetup complete.")
    print("\nNext steps:")
    print("  1. Open your Google Sheet and add competitors to 'Competitor Tracker' (YouTube URL column)")
    print("  2. Run: python -m operations.channel_analyst  (builds brand voice)")
    print("  3. Run: python -m operations.run_daily_pipeline  (runs everything)")


if __name__ == "__main__":
    main()
