"""
Agent 2: Trend Scout
Scans competitor channels for outlier videos from the last 5 days.

Usage:
    python -m operations.trend_scout
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date
from dotenv import load_dotenv
from tools.youtube_api import get_channel_id, get_channel_stats, get_recent_videos, calculate_outlier_score
from tools.sheets_api import append_rows, read_all, TABS
from tools.logger import setup_logger

load_dotenv()
logger = setup_logger("trend_scout")

MIN_OUTLIER_SCORE = 0.8  # at least 80% of the channel's average to qualify
SCAN_DAYS = 14


def get_monitored_channel_urls() -> list[str]:
    rows = read_all(TABS["competitors"])
    # Column index 4 = "YouTube URL" (0-based)
    urls = [row[4].strip() for row in rows[1:] if len(row) >= 5 and row[4].strip()]
    return urls


def scan_channels(channel_urls: list[str]) -> list[dict]:
    outliers = []

    for url in channel_urls:
        try:
            cid = get_channel_id(url)
            stats = get_channel_stats(cid)
            avg = stats["avg_views"]

            if avg == 0:
                logger.debug(f"Skipping {stats['title']}: no view data")
                continue

            recent = get_recent_videos(cid, days=SCAN_DAYS, uploads_playlist=stats.get("uploads_playlist", ""))

            for video in recent:
                score = calculate_outlier_score(video["views"], avg)
                if score >= MIN_OUTLIER_SCORE:
                    outliers.append(
                        {
                            **video,
                            "outlier_score": score,
                            "channel_avg_views": avg,
                            "channel_subscribers": stats["subscribers"],
                        }
                    )
                    logger.info(
                        f"  Outlier: {video['title'][:55]} | "
                        f"{score}x | {video['views']:,} views"
                    )

        except Exception as e:
            logger.warning(f"  Failed to scan {url}: {e}")

    return sorted(outliers, key=lambda x: x["outlier_score"], reverse=True)


def save_outliers(outliers: list[dict]) -> None:
    if not outliers:
        logger.info("No outliers to save")
        return

    today = str(date.today())
    rows = [
        [
            today,
            "YouTube",
            o["channel_title"],
            o["title"],
            o["views"],
            o["outlier_score"],
            o["url"],
            "",  # Hook Transcript — filled later by Script Writer or manually
        ]
        for o in outliers
    ]
    append_rows(TABS["outliers"], rows)
    logger.info(f"Saved {len(rows)} outliers to sheet")


def run() -> list[dict]:
    logger.info("=== Trend Scout starting ===")

    channel_urls = get_monitored_channel_urls()
    if not channel_urls:
        logger.warning(
            "No competitor channels found. "
            "Add channels to the 'Competitor Tracker' tab first."
        )
        return []

    logger.info(f"Scanning {len(channel_urls)} channels (last {SCAN_DAYS} days)...")
    outliers = scan_channels(channel_urls)
    save_outliers(outliers)

    logger.info(f"=== Trend Scout complete: {len(outliers)} outliers found ===")
    return outliers


if __name__ == "__main__":
    run()
