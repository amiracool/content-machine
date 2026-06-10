"""
Agent 4: Thumbnail Designer
Generates 3 thumbnail concepts via DALL-E 3 based on the top outlier.

Usage:
    python -m operations.thumbnail_designer
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import re
import requests
from datetime import date
from dotenv import load_dotenv
from tools.sheets_api import read_all, write_range, TABS, read_brand_voice
from tools.llm_api import complete
from tools.image_api import generate_thumbnail
from tools.logger import setup_logger

load_dotenv()
logger = setup_logger("thumbnail_designer")

THUMBNAILS_DIR = Path(".tmp/thumbnails")


def get_top_outlier() -> dict | None:
    rows = read_all(TABS["outliers"])
    if len(rows) < 2:
        return None

    today = str(date.today())
    data_rows = [r for r in rows[1:] if r and len(r) >= 7]
    today_rows = [r for r in data_rows if r[0] == today]
    candidates = today_rows if today_rows else data_rows

    if not candidates:
        return None

    try:
        top = max(candidates, key=lambda r: float(r[5]) if len(r) > 5 else 0)
    except (ValueError, IndexError):
        top = candidates[0]

    return {
        "title": top[3] if len(top) > 3 else "",
        "url": top[6] if len(top) > 6 else "",
        "channel": top[2] if len(top) > 2 else "",
        "score": top[5] if len(top) > 5 else "",
        "views": top[4] if len(top) > 4 else "",
    }


def download_reference_thumbnail(video_url: str) -> Path | None:
    try:
        video_id = video_url.split("v=")[-1].split("&")[0]
        for quality in ["maxresdefault", "hqdefault"]:
            url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                path = THUMBNAILS_DIR / "reference.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(resp.content)
                logger.info(f"Reference thumbnail saved: {path}")
                return path
    except Exception as e:
        logger.warning(f"Could not download reference thumbnail: {e}")
    return None


def generate_concepts(outlier: dict, brand_voice: dict) -> list[dict]:
    prompt = f"""You are a YouTube thumbnail strategist. Generate 3 distinct thumbnail concepts.

VIRAL VIDEO TO STUDY:
Title: {outlier['title']}
Channel: {outlier['channel']}
Performance: {outlier['score']}x above average ({outlier['views']} views)

BRAND VOICE:
Tone: {brand_voice.get('Tone', 'bold, direct')}
Thumbnail style: {brand_voice.get('Thumbnail Style', 'high contrast, emotional, text overlay')}
Ideal viewer: {brand_voice.get('ICA', '')}

Generate 3 thumbnail concepts. For each provide:

CONCEPT 1:
Prompt: [Complete DALL-E 3 prompt. Must include: "YouTube thumbnail, photorealistic, high contrast" + composition + colors + facial expression if applicable + bold text overlay placement + background]
Text: [5 words max — the overlay text on the thumbnail]
Strategy: [One sentence on why this drives clicks]

CONCEPT 2:
Prompt: [...]
Text: [...]
Strategy: [...]

CONCEPT 3:
Prompt: [...]
Text: [...]
Strategy: [...]

Make each concept visually distinct. One should use emotion/face, one should use bold graphic/text only, one should use a scene or result."""

    response = complete(prompt, max_tokens=1200)
    return _parse_concepts(response)


def _parse_concepts(text: str) -> list[dict]:
    # Save raw response for debugging
    debug_path = THUMBNAILS_DIR / "last-concepts-raw.txt"
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_text(text, encoding="utf-8")

    concepts = []
    # Split on CONCEPT N: or **CONCEPT N:** or CONCEPT N (various formats Claude uses)
    blocks = re.split(r"\*{0,2}CONCEPT\s*\d+\*{0,2}:?\s*\n?", text, flags=re.IGNORECASE)

    for block in blocks[1:]:  # skip preamble before first concept
        concept: dict = {}
        current_key = None
        current_val: list[str] = []

        for line in block.split("\n"):
            line = line.strip().lstrip("*").strip()
            if not line:
                continue

            lower = line.lower()
            if lower.startswith("prompt:"):
                if current_key:
                    concept[current_key] = " ".join(current_val).strip()
                current_key = "prompt"
                current_val = [line[7:].strip()]
            elif lower.startswith("text:"):
                if current_key:
                    concept[current_key] = " ".join(current_val).strip()
                current_key = "text"
                current_val = [line[5:].strip()]
            elif lower.startswith("strategy:"):
                if current_key:
                    concept[current_key] = " ".join(current_val).strip()
                current_key = "strategy"
                current_val = [line[9:].strip()]
            elif current_key:
                current_val.append(line)

        if current_key:
            concept[current_key] = " ".join(current_val).strip()

        if concept.get("prompt"):
            concepts.append(concept)

    return concepts[:3]


def run() -> list[Path]:
    logger.info("=== Thumbnail Designer starting ===")

    outlier = get_top_outlier()
    if not outlier:
        logger.warning("No outliers found. Skipping thumbnail generation.")
        return []

    brand_voice = read_brand_voice()
    today = str(date.today())
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Designing thumbnails for: {outlier['title'][:55]}")
    download_reference_thumbnail(outlier["url"])

    concepts = generate_concepts(outlier, brand_voice)
    logger.info(f"Generated {len(concepts)} thumbnail concepts")

    # Save analysis markdown
    analysis_lines = [f"# Thumbnail Analysis — {today}\n\n"]
    analysis_lines += [
        f"## Concept {i+1}\n**Prompt:** {c.get('prompt','')}\n**Text:** {c.get('text','')}\n**Strategy:** {c.get('strategy','')}\n\n"
        for i, c in enumerate(concepts)
    ]
    (THUMBNAILS_DIR / f"{today}-thumbnail-analysis.md").write_text(
        "".join(analysis_lines), encoding="utf-8"
    )

    paths = []
    for i, concept in enumerate(concepts, 1):
        prompt_text = concept.get("prompt", "")
        if not prompt_text:
            continue
        output_path = THUMBNAILS_DIR / f"{today}-thumbnail-{i}.png"
        try:
            path = generate_thumbnail(prompt_text, output_path)
            paths.append(path)
        except Exception as e:
            logger.error(f"Failed to generate thumbnail {i}: {e}")

    # Mark thumbnail status in Content Calendar
    if paths:
        cal_rows = read_all(TABS["calendar"])
        for i, row in enumerate(cal_rows[1:], start=2):
            if row and row[0] == today:
                write_range(TABS["calendar"], f"E{i}", [["Ready"]])
                break

    logger.info(f"=== Thumbnail Designer complete: {len(paths)} thumbnails generated ===")
    return paths


if __name__ == "__main__":
    run()
