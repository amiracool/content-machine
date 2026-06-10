import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
from tools.youtube_api import get_channel_id, get_channel_stats, get_recent_videos, calculate_outlier_score

channels = [
    "https://www.youtube.com/@adhdvision",
    "https://www.youtube.com/@ADHD_love",
    "https://www.youtube.com/@TheNeurocuriosityClub",
    "https://www.youtube.com/@ADHD_Chatter_Podcast",
]

for url in channels:
    try:
        cid = get_channel_id(url)
        stats = get_channel_stats(cid)
        recent = get_recent_videos(cid, days=30, uploads_playlist=stats.get("uploads_playlist", ""))
        print(f"\n{stats['title']} | avg {stats['avg_views']:,} views | {len(recent)} videos in last 30d")
        for v in recent[:4]:
            score = calculate_outlier_score(v["views"], stats["avg_views"])
            print(f"  {score}x | {v['views']:,} views | {v['title'][:60]}")
    except Exception as e:
        print(f"Error on {url}: {e}")
