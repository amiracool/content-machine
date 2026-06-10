"""
Agent 3: Script Writer
Picks the top outlier and writes a full script in your brand voice.

Usage:
    python -m operations.script_writer
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date
from dotenv import load_dotenv
from tools.sheets_api import read_all, append_rows, TABS, read_brand_voice
from tools.llm_api import complete
from tools.logger import setup_logger

load_dotenv()
logger = setup_logger("script_writer")

SCRIPTS_DIR = Path(".tmp/scripts")


def get_top_outlier() -> dict | None:
    rows = read_all(TABS["outliers"])
    if len(rows) < 2:
        return None

    today = str(date.today())
    data_rows = [r for r in rows[1:] if r and len(r) >= 7]

    # Prefer today's outliers; fall back to most recent
    today_rows = [r for r in data_rows if r[0] == today]
    candidates = today_rows if today_rows else data_rows

    if not candidates:
        return None

    try:
        top = max(candidates, key=lambda r: float(r[5]) if len(r) > 5 else 0)
    except (ValueError, IndexError):
        top = candidates[0]

    return {
        "date": top[0],
        "channel": top[2] if len(top) > 2 else "",
        "title": top[3] if len(top) > 3 else "",
        "views": top[4] if len(top) > 4 else "",
        "score": top[5] if len(top) > 5 else "",
        "url": top[6] if len(top) > 6 else "",
    }


def generate_hooks(outlier: dict, brand_voice: dict) -> list[str]:
    prompt = f"""You are a YouTube hook specialist. Generate 5 high-converting hooks for a video.

REFERENCE VIDEO (this went viral):
Title: {outlier['title']}
Channel: {outlier['channel']}
Views: {outlier['views']} ({outlier['score']}x the channel average)

BRAND VOICE:
Tone: {brand_voice.get('Tone', 'engaging, direct, educational')}
Ideal viewer: {brand_voice.get('ICA', 'curious learners')}
Hooks that work: {brand_voice.get('Hooks That Work', 'problem-solution, curiosity gap')}
Words to use: {brand_voice.get('Words You Use', '')}
Words to avoid: {brand_voice.get('Words You Avoid', '')}

Generate exactly 5 hooks. Rules:
- Under 25 words each
- Create immediate curiosity or name a painful problem
- Feel natural, not clickbait
- Match the brand voice exactly

Output each hook on its own line, numbered 1-5. Nothing else."""

    response = complete(prompt, max_tokens=400)
    hooks = []
    for line in response.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and ("." in line or ")" in line):
            _, _, hook = line.partition(line[1])  # split after first digit
            hook = hook.strip(". )").strip()
            if hook:
                hooks.append(hook)
    return hooks[:5]


def write_script(outlier: dict, brand_voice: dict, hooks: list[str]) -> str:
    hooks_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(hooks))

    prompt = f"""You are an expert YouTube scriptwriter. Write a complete video script.

REFERENCE VIDEO (it overperformed by {outlier['score']}x):
Title: {outlier['title']}
Channel: {outlier['channel']}
URL: {outlier['url']}

BRAND VOICE:
Tone: {brand_voice.get('Tone', '')}
Topics/pillars: {brand_voice.get('Topics', '')}
Ideal viewer: {brand_voice.get('ICA', '')}
Words to use: {brand_voice.get('Words You Use', '')}
Words to avoid: {brand_voice.get('Words You Avoid', '')}
Title patterns: {brand_voice.get('Title Patterns', '')}

HOOKS (pick the strongest one to open with):
{hooks_text}

Write the complete script using this exact structure:

## HOOK (0–30 seconds)
[Use the best hook above. Make it impossible to scroll past.]

## SETUP (30–90 seconds)
[Identify the viewer's situation. Name their exact problem. Introduce the opportunity. Promise the specific result they'll get.]

## BODY

### Section 1: [Name the point]
[Main point in 1-2 sentences]
[Analogy or concrete example]
[B-ROLL CUE: what to show on screen]
[Transition to next section]

### Section 2: [Name the point]
[Repeat structure above]

### Section 3: [Name the point]
[Repeat structure above]

(Add sections 4-5 if the topic needs it)

## CTA (final 30 seconds)
[One clear subscribe reason. Recommend one specific next video to watch.]

---
Write conversationally. Use short sentences. Include [B-ROLL CUE: ...] markers throughout.
Target: 1,200–2,000 words in the body sections."""

    return complete(prompt, max_tokens=4096)


def save_script(script: str, outlier: dict, hooks: list[str]) -> Path:
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    today = str(date.today())

    content = f"# Script — {today}\n\n"
    content += f"**Reference:** [{outlier['title']}]({outlier['url']})\n"
    content += f"**Channel:** {outlier['channel']}\n"
    content += f"**Outlier Score:** {outlier['score']}x\n\n"
    content += "---\n\n## HOOKS\n\n"
    content += "\n".join(f"{i+1}. {h}" for i, h in enumerate(hooks))
    content += "\n\n---\n\n"
    content += script

    path = SCRIPTS_DIR / f"{today}-script.md"
    path.write_text(content, encoding="utf-8")
    logger.info(f"Script saved: {path}")
    return path


def update_calendar(outlier: dict, hooks: list[str]) -> None:
    today = str(date.today())
    append_rows(
        TABS["calendar"],
        [[
            today,
            outlier["title"],
            hooks[0] if hooks else "",
            "Ready",
            "Pending",
            "Not Published",
        ]],
    )


def run() -> dict | None:
    logger.info("=== Script Writer starting ===")

    outlier = get_top_outlier()
    if not outlier:
        logger.warning("No outliers found in sheet. Skipping script generation.")
        return None

    brand_voice = read_brand_voice()
    if not brand_voice:
        logger.warning("Brand Voice sheet is empty. Run Channel Analyst first for best results.")

    logger.info(f"Writing script based on: {outlier['title'][:60]}")

    hooks = generate_hooks(outlier, brand_voice)
    logger.info(f"Generated {len(hooks)} hooks")

    script = write_script(outlier, brand_voice, hooks)
    path = save_script(script, outlier, hooks)
    update_calendar(outlier, hooks)

    logger.info("=== Script Writer complete ===")
    return {"outlier": outlier, "hooks": hooks, "script": script, "path": str(path)}


if __name__ == "__main__":
    run()
