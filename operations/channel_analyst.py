"""
Agent 1: Channel Analyst
Run once to build brand voice + competitor intelligence. Re-run weekly.

Usage:
    python -m operations.channel_analyst
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from tools.youtube_api import get_channel_id, get_channel_stats, get_recent_videos
from tools.sheets_api import write_range, append_rows, read_competitors, TABS
from tools.llm_api import complete
from tools.logger import setup_logger

load_dotenv()
logger = setup_logger("channel_analyst")


def analyze_own_channel() -> dict:
    channel_url = os.getenv("YOUTUBE_CHANNEL_URL", "")
    if not channel_url:
        logger.error("YOUTUBE_CHANNEL_URL not set in .env")
        return {}

    logger.info(f"Analyzing own channel: {channel_url}")
    channel_id = get_channel_id(channel_url)
    stats = get_channel_stats(channel_id)
    recent = get_recent_videos(channel_id, days=90)
    logger.info(
        f"  {stats['title']} | {stats['subscribers']:,} subs | "
        f"avg {stats['avg_views']:,} views | {len(recent)} recent videos"
    )
    return {"stats": stats, "recent_videos": recent}


def analyze_competitors() -> list[dict]:
    competitors = read_competitors()
    if not competitors:
        logger.warning(
            "No competitors in sheet. Add rows to 'Competitor Tracker' tab first."
        )
        return []

    results = []
    for comp in competitors:
        url = comp.get("YouTube URL", "").strip()
        if not url:
            continue
        try:
            cid = get_channel_id(url)
            stats = get_channel_stats(cid)
            recent = get_recent_videos(cid, days=30)
            results.append({"url": url, "stats": stats, "recent_videos": recent})
            logger.info(f"  Competitor: {stats['title']} | avg {stats['avg_views']:,} views")
        except Exception as e:
            logger.warning(f"  Failed to analyze {url}: {e}")

    return results


def build_brand_voice(own_data: dict, competitor_data: list[dict]) -> str:
    own_stats = own_data.get("stats", {})
    own_videos = own_data.get("recent_videos", [])

    own_titles = "\n".join(
        f"  - {v['title']} ({v['views']:,} views)"
        for v in sorted(own_videos, key=lambda x: x["views"], reverse=True)[:20]
    )

    comp_summary = ""
    for c in competitor_data[:5]:
        top = sorted(c.get("recent_videos", []), key=lambda x: x["views"], reverse=True)[:3]
        comp_summary += f"\n  {c['stats']['title']} ({c['stats']['subscribers']:,} subs):\n"
        for v in top:
            comp_summary += f"    - {v['title']} ({v['views']:,} views)\n"

    prompt = f"""You are a YouTube channel strategy expert. Analyze this data and create a brand voice document.

MY CHANNEL: {own_stats.get('title', 'Unknown')}
Subscribers: {own_stats.get('subscribers', 0):,}
Average views: {own_stats.get('avg_views', 0):,}

MY TOP RECENT VIDEOS:
{own_titles or '  (no recent videos found)'}

TOP COMPETITOR VIDEOS:
{comp_summary or '  (no competitor data)'}

Based on this data, create a brand voice document. Output exactly these fields, one per line:
- Tone: [describe the communication tone]
- ICA: [ideal content audience — who watches and why]
- Topics: [3-5 content pillars, comma-separated]
- Hooks That Work: [title/hook patterns that drove high views]
- Words You Use: [phrases and style markers that feel authentic]
- Words You Avoid: [things that feel off-brand]
- Title Patterns: [structural patterns from best-performing titles]
- Thumbnail Style: [visual approach that works for this channel]

Be specific and actionable. Base everything on the actual data above."""

    return complete(prompt)


def update_brand_voice_sheet(brand_voice_text: str):
    rows = []
    for line in brand_voice_text.strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip("- •").strip()
            value = value.strip()
            if key and value:
                rows.append([key, value])

    if rows:
        write_range(TABS["brand_voice"], "A2", rows)
        logger.info(f"Updated Brand Voice sheet with {len(rows)} entries")


def update_competitor_sheet(competitor_data: list[dict]):
    rows = [
        [
            c["stats"]["title"],
            c["stats"]["subscribers"],
            c["stats"]["avg_views"],
            "YouTube",
            c["url"],
        ]
        for c in competitor_data
    ]
    if rows:
        write_range(TABS["competitors"], "A2", rows)
        logger.info(f"Updated Competitor Tracker with {len(rows)} channels")


def run():
    logger.info("=== Channel Analyst starting ===")

    own_data = analyze_own_channel()
    competitor_data = analyze_competitors()

    if own_data:
        logger.info("Building brand voice document...")
        brand_voice = build_brand_voice(own_data, competitor_data)
        update_brand_voice_sheet(brand_voice)

    if competitor_data:
        update_competitor_sheet(competitor_data)

    logger.info("=== Channel Analyst complete ===")


if __name__ == "__main__":
    run()
