"""
Agent 7: Dashboard
Generates 4 local HTML tools: dashboard, recording sheet, teleprompter, viewer.

Usage:
    python -m operations.dashboard
"""
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date
from dotenv import load_dotenv
from tools.sheets_api import read_all, TABS
from tools.logger import setup_logger

load_dotenv()
logger = setup_logger("dashboard")

TMP_DIR = Path(".tmp")


def _load_data() -> dict:
    today = str(date.today())

    outliers = []
    for row in read_all(TABS["outliers"])[1:]:
        if row and row[0] == today and len(row) >= 7:
            try:
                score = float(row[5])
            except (ValueError, IndexError):
                score = 0.0
            outliers.append(
                {
                    "channel": row[2] if len(row) > 2 else "",
                    "title": row[3] if len(row) > 3 else "",
                    "score": row[5] if len(row) > 5 else "",
                    "url": row[6] if len(row) > 6 else "#",
                    "_score": score,
                }
            )
    outliers.sort(key=lambda x: x["_score"], reverse=True)

    cal = None
    for row in read_all(TABS["calendar"])[1:]:
        if row and row[0] == today and len(row) >= 4:
            cal = {
                "title": row[1] if len(row) > 1 else "TBD",
                "hook": row[2] if len(row) > 2 else "TBD",
                "script_status": row[3] if len(row) > 3 else "Pending",
                "thumbnail_status": row[4] if len(row) > 4 else "Pending",
            }
            break

    script = ""
    script_path = TMP_DIR / "scripts" / f"{today}-script.md"
    if script_path.exists():
        script = script_path.read_text(encoding="utf-8")

    thumbnails = sorted((TMP_DIR / "thumbnails").glob(f"{today}-thumbnail-*.png"))

    return {
        "today": today,
        "outliers": outliers,
        "cal": cal or {},
        "script": script,
        "thumbnails": [p.name for p in thumbnails],  # filenames only; copied to docs/thumbnails/
    }


def _dashboard(d: dict) -> str:
    cal = d["cal"]
    outlier_cards = "".join(
        f'<div class="card"><span class="score">{o["score"]}x</span>'
        f'<a href="{o["url"]}" target="_blank">{o["title"][:72]}</a>'
        f'<span class="ch">{o["channel"]}</span></div>'
        for o in d["outliers"][:5]
    )
    thumb_imgs = "".join(
        f'<img src="thumbnails/{p}" style="width:100%;max-width:320px;border-radius:8px;margin:6px;" />'
        for p in d["thumbnails"]
    ) or '<p style="color:#6B7280">No thumbnails yet</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Content Machine — {d['today']}</title>
<style>
  *{{box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0A0A0A;color:#E5E7EB;margin:0;padding:20px}}
  h1{{color:#A78BFA;margin-bottom:4px}}h2{{color:#C4B5FD;border-bottom:1px solid #27272A;padding-bottom:8px;font-size:15px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
  .panel{{background:#18181B;border-radius:12px;padding:18px;border:1px solid #27272A}}
  .card{{background:#27272A;border-radius:8px;padding:12px;margin:6px 0;display:flex;flex-direction:column;gap:3px}}
  .score{{color:#34D399;font-weight:bold;font-size:20px}}.ch{{color:#71717A;font-size:12px}}
  a{{color:#818CF8;text-decoration:none}}a:hover{{text-decoration:underline}}
  .pill{{display:inline-block;padding:3px 10px;border-radius:4px;font-size:12px;background:#052E16;color:#6EE7B7;margin:2px}}
  .nav{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}}
  .btn{{background:#4F46E5;color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600}}
  .full{{grid-column:1/-1}}
</style>
</head>
<body>
<h1>Content Machine</h1>
<p style="color:#71717A;margin-top:0;font-size:13px">{d['today']}</p>
<div class="nav">
  <a href="recording.html" class="btn">Recording Sheet</a>
  <a href="teleprompter.html" class="btn">Teleprompter</a>
  <a href="viewer.html" class="btn">Viewer Script</a>
</div>
<div class="grid">
  <div class="panel">
    <h2>Today's Video</h2>
    <p style="font-size:15px;font-weight:600;margin:0 0 6px">{cal.get('title','TBD')}</p>
    <p style="color:#A1A1AA;font-style:italic;font-size:13px;margin:0 0 10px">{cal.get('hook','—')}</p>
    <span class="pill">Script: {cal.get('script_status','Pending')}</span>
    <span class="pill" style="background:#1E3A5F;color:#60A5FA;">Thumbnails: {cal.get('thumbnail_status','Pending')}</span>
  </div>
  <div class="panel">
    <h2>Thumbnails</h2>{thumb_imgs}
  </div>
  <div class="panel full">
    <h2>Top Outliers</h2>
    {outlier_cards or '<p style="color:#71717A">No outliers scanned yet — run Trend Scout</p>'}
  </div>
</div>
</body></html>"""


def _recording(d: dict) -> str:
    cal = d["cal"]
    script = d["script"]
    hook = cal.get("hook", "")
    if not hook and "## HOOK" in script:
        hook = script.split("## HOOK")[1].split("##")[0].strip()[:200]

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Recording Sheet</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:750px;margin:40px auto;padding:20px;background:#fff;color:#111}}
  h1{{color:#4F46E5}}a{{color:#4F46E5}}
  .box{{margin:20px 0;padding:16px;border-radius:8px;border-left:4px solid #4F46E5;background:#F5F3FF}}
  .hook{{border-left-color:#059669;background:#F0FDF4}}.cta{{border-left-color:#D97706;background:#FFFBEB}}
  ul{{list-style:none;padding:0}}li{{padding:8px 12px;margin:4px 0;background:#EEF2FF;border-radius:6px;cursor:pointer}}
  li:hover{{background:#E0E7FF}}li::before{{content:"☐  "}}
  .big{{font-size:20px;font-weight:700;line-height:1.4}}
  .cta-btn{{display:inline-block;margin-top:20px;background:#4F46E5;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600}}
</style>
</head>
<body>
<h1>Recording Cheat Sheet</h1>
<p style="color:#6B7280">{d['today']} — <a href="dashboard.html">← Dashboard</a></p>
<div class="box"><strong>VIDEO:</strong> {cal.get('title','TBD')}</div>
<div class="box hook"><h3 style="margin-top:0">HOOK — say this first</h3><p class="big">{hook or 'See script for hook'}</p></div>
<div class="box">
  <h3 style="margin-top:0">Before You Hit Record</h3>
  <ul>
    <li>Camera angle &amp; framing set</li>
    <li>Lighting checked (no harsh shadows)</li>
    <li>Audio test done (no echo)</li>
    <li>Teleprompter loaded and scrolling</li>
    <li>Background clean and branded</li>
    <li>Phone on silent / notifications off</li>
    <li>Water nearby</li>
    <li>Record 3 takes of the hook</li>
  </ul>
</div>
<div class="box cta"><h3 style="margin-top:0">CTA — say at the end</h3>
<p>If this helped you, subscribe — I post [your cadence] on [your topic]. Next video: <strong>[recommend a specific related video]</strong></p></div>
<a href="teleprompter.html" class="cta-btn">Open Teleprompter →</a>
</body></html>"""


def _teleprompter(d: dict) -> str:
    script = d["script"]
    # Strip markdown headers, keep B-roll cues highlighted
    display = re.sub(r"^#{1,3}\s+", "", script, flags=re.MULTILINE)
    display = re.sub(
        r"\[B-ROLL CUE[^\]]*\]",
        '<span class="broll">[B-ROLL]</span>',
        display,
    )
    display = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", display)
    display = display.replace("\n\n", "</p><p>").replace("\n", " ")

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Teleprompter</title>
<style>
  body{{background:#000;color:#fff;font-family:'Georgia',Georgia,serif;font-size:30px;line-height:1.9;padding:40px 100px;max-width:1100px;margin:0 auto}}
  p{{margin:22px 0}}.broll{{color:#FBBF24;font-size:0.7em;font-family:sans-serif}}
  strong{{color:#A78BFA}}
  .ctrl{{position:fixed;bottom:20px;right:20px;display:flex;gap:8px;background:rgba(0,0,0,0.7);padding:10px;border-radius:10px}}
  .btn{{background:#4F46E5;color:#fff;border:none;padding:10px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600}}
  #spd{{color:#9CA3AF;font-size:12px;padding:10px;align-self:center}}
  .back{{position:fixed;top:16px;left:16px;color:#71717A;font-size:13px;text-decoration:none}}
</style>
</head>
<body>
<a href="dashboard.html" class="back">← Dashboard</a>
<p>{display}</p>
<div class="ctrl">
  <button class="btn" onclick="adj(-0.5)">− Slower</button>
  <span id="spd">1 px/s</span>
  <button class="btn" onclick="adj(0.5)">+ Faster</button>
  <button class="btn" id="tog" onclick="toggle()">▶ Start</button>
</div>
<script>
let sp=1,on=false,iv=null;
function toggle(){{on=!on;document.getElementById('tog').textContent=on?'⏸ Pause':'▶ Start';if(on)iv=setInterval(()=>window.scrollBy(0,sp),50);else clearInterval(iv);}}
function adj(d){{sp=Math.max(0.5,Math.min(8,sp+d));document.getElementById('spd').textContent=sp+'px/s';}}
</script>
</body></html>"""


def _viewer(d: dict) -> str:
    script = d["script"]
    # Convert markdown to basic HTML
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", script, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\[B-ROLL CUE[^\]]*\]", '<em style="color:#D97706">[B-ROLL]</em>', html)
    html = re.sub(r"\n\n", "</p><p>", html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Script Viewer — {d['today']}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:780px;margin:40px auto;padding:20px;background:#F9FAFB;color:#111;line-height:1.8;font-size:16px}}
  h1,h2{{color:#4F46E5}}h3{{color:#6D28D9}}p{{margin:14px 0}}
  a{{color:#4F46E5}}strong{{color:#111}}
</style>
</head>
<body>
<h1>Script — {d['today']}</h1>
<p><a href="dashboard.html">← Dashboard</a> &nbsp;|&nbsp; <a href="teleprompter.html">Teleprompter →</a></p>
<hr>
<p>{html}</p>
</body></html>"""


DOCS_DIR = Path("docs")


def run() -> dict:
    logger.info("=== Dashboard starting ===")
    TMP_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)

    try:
        data = _load_data()
    except Exception as e:
        logger.error(f"Failed to load sheet data: {e}")
        data = {
            "today": str(date.today()),
            "outliers": [],
            "cal": {},
            "script": "(no script yet — run Script Writer)",
            "thumbnails": [],
        }

    files = {
        "dashboard.html": _dashboard(data),
        "recording.html": _recording(data),
        "teleprompter.html": _teleprompter(data),
        "viewer.html": _viewer(data),
    }

    for filename, content in files.items():
        # Write to .tmp/ (local) and docs/ (GitHub Pages)
        (TMP_DIR / filename).write_text(content, encoding="utf-8")
        (DOCS_DIR / filename).write_text(content, encoding="utf-8")
        logger.info(f"Generated: {TMP_DIR / filename}")

    # index.html → redirect to dashboard so the Pages root URL works
    (DOCS_DIR / "index.html").write_text(
        '<meta http-equiv="refresh" content="0; url=dashboard.html">',
        encoding="utf-8",
    )

    # .nojekyll stops GitHub Pages from running Jekyll (avoids build errors)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    # Copy today's thumbnail images into docs/thumbnails/
    thumb_src = TMP_DIR / "thumbnails"
    thumb_dst = DOCS_DIR / "thumbnails"
    thumb_dst.mkdir(exist_ok=True)
    today = data["today"]
    for src in sorted(thumb_src.glob(f"{today}-thumbnail-*.png")):
        shutil.copy2(src, thumb_dst / src.name)
        logger.info(f"Copied thumbnail: {src.name}")

    logger.info("=== Dashboard complete ===")
    return {name: str(TMP_DIR / name) for name in files}


if __name__ == "__main__":
    result = run()
    print("\nFiles generated:")
    for name, path in result.items():
        print(f"  {path}")
