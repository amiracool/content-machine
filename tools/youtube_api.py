import os
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from tools.retry import retry
from tools.logger import setup_logger
from tools.quota_tracker import increment, check_limit

logger = setup_logger("youtube_api")


def _client():
    return build("youtube", "v3", developerKey=os.getenv("YOUTUBE_API_KEY"))


@retry(max_attempts=3)
def get_channel_id(channel_url: str) -> str:
    yt = _client()
    url = channel_url.strip().rstrip("/")

    if "@" in url:
        handle = url.split("@")[-1]
        # forHandle is cheaper (1 unit) and doesn't require search permissions
        resp = yt.channels().list(part="id", forHandle=handle).execute()
        increment("youtube", 1)
        items = resp.get("items", [])
        if items:
            return items[0]["id"]
    elif "channel/" in url:
        return url.split("channel/")[-1].split("/")[0]

    raise ValueError(f"Could not resolve channel ID from: {channel_url}")


@retry(max_attempts=3)
def get_channel_stats(channel_id: str) -> dict:
    if not check_limit("youtube"):
        raise RuntimeError("YouTube daily quota exhausted")

    yt = _client()
    resp = (
        yt.channels()
        .list(part="snippet,statistics,contentDetails", id=channel_id)
        .execute()
    )
    increment("youtube", 1)

    item = resp["items"][0]
    stats = item["statistics"]
    video_count = max(int(stats.get("videoCount", 1)), 1)
    uploads_playlist = (
        item.get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads", "")
    )
    return {
        "channel_id": channel_id,
        "title": item["snippet"]["title"],
        "subscribers": int(stats.get("subscriberCount", 0)),
        "total_views": int(stats.get("viewCount", 0)),
        "video_count": video_count,
        "avg_views": int(stats.get("viewCount", 0)) // video_count,
        "uploads_playlist": uploads_playlist,
    }


@retry(max_attempts=3)
def get_recent_videos(channel_id: str, days: int = 5, uploads_playlist: str = "") -> list[dict]:
    """Fetch recent videos via the uploads playlist — no search quota, no 403s."""
    if not check_limit("youtube"):
        raise RuntimeError("YouTube daily quota exhausted")

    yt = _client()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Resolve uploads playlist if not provided
    if not uploads_playlist:
        ch_resp = yt.channels().list(part="contentDetails", id=channel_id).execute()
        increment("youtube", 1)
        if not ch_resp.get("items"):
            return []
        uploads_playlist = (
            ch_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        )

    # Walk the uploads playlist until we go past the cutoff
    video_ids = []
    next_page = None

    while len(video_ids) < 20:
        kwargs: dict = dict(
            part="snippet,contentDetails",
            playlistId=uploads_playlist,
            maxResults=50,
        )
        if next_page:
            kwargs["pageToken"] = next_page

        pl_resp = yt.playlistItems().list(**kwargs).execute()
        increment("youtube", 1)

        past_cutoff = False
        for item in pl_resp.get("items", []):
            published_str = item["snippet"]["publishedAt"]
            pub_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            if pub_dt < cutoff:
                past_cutoff = True
                break
            video_ids.append(item["contentDetails"]["videoId"])

        next_page = pl_resp.get("nextPageToken")
        if past_cutoff or not next_page:
            break

    if not video_ids:
        return []

    # Batch fetch stats (1 unit per call)
    stats_resp = (
        yt.videos()
        .list(part="statistics,snippet", id=",".join(video_ids[:10]))
        .execute()
    )
    increment("youtube", 1)

    result = []
    for item in stats_resp.get("items", []):
        thumbs = item["snippet"]["thumbnails"]
        thumb_url = (
            thumbs.get("maxres", thumbs.get("high", thumbs.get("medium", {})))
            .get("url", "")
        )
        result.append(
            {
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "channel_id": channel_id,
                "channel_title": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"],
                "views": int(item["statistics"].get("viewCount", 0)),
                "thumbnail_url": thumb_url,
                "url": f"https://www.youtube.com/watch?v={item['id']}",
            }
        )

    return result


def calculate_outlier_score(video_views: int, channel_avg_views: int) -> float:
    if channel_avg_views == 0:
        return 0.0
    return round(video_views / channel_avg_views, 2)
