"""
Agent 8: Pipeline Runner
Orchestrates all daily agents in sequence.

Usage:
    python -m operations.run_daily_pipeline              # full pipeline
    python -m operations.run_daily_pipeline trend        # trend scout only
    python -m operations.run_daily_pipeline trend script # trend + script
"""
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from tools.logger import setup_logger
from tools.quota_tracker import report as quota_report

load_dotenv()
logger = setup_logger("pipeline")

VALID_STEPS = ["trend", "script", "thumbnails", "report", "dashboard"]


def _run_step(label: str, func, *args, **kwargs):
    logger.info(f"┌─ Starting: {label}")
    start = datetime.now()
    try:
        result = func(*args, **kwargs)
        elapsed = (datetime.now() - start).seconds
        logger.info(f"└─ Done: {label} ({elapsed}s)")
        return result
    except Exception as e:
        logger.error(f"└─ FAILED: {label}: {e}")
        logger.debug(traceback.format_exc())
        return None


def run(steps: list[str] | None = None):
    from operations import trend_scout, script_writer, thumbnail_designer, daily_reporter, dashboard

    active = steps or VALID_STEPS
    unknown = [s for s in active if s not in VALID_STEPS]
    if unknown:
        logger.error(f"Unknown steps: {unknown}. Valid: {VALID_STEPS}")
        sys.exit(1)

    start = datetime.now()
    logger.info(f"{'='*50}")
    logger.info(f"PIPELINE START — {start.strftime('%Y-%m-%d %H:%M')} — steps: {active}")
    logger.info(f"{'='*50}")

    results: dict = {}

    # Trend Scout
    if "trend" in active:
        outliers = _run_step("Trend Scout", trend_scout.run)
        results["trend"] = outliers
        if not outliers:
            logger.warning("No outliers found today. Script Writer will use most recent outlier.")

    # Script Writer
    if "script" in active:
        script_data = _run_step("Script Writer", script_writer.run)
        results["script"] = script_data
        if script_data is None:
            logger.warning("Script generation failed or skipped.")

    # Thumbnail Designer (skip only if script failed AND it was requested)
    if "thumbnails" in active:
        if "script" in active and results.get("script") is None:
            logger.warning("Skipping Thumbnail Designer — no script was generated.")
            results["thumbnails"] = []
        else:
            thumb_paths = _run_step("Thumbnail Designer", thumbnail_designer.run)
            results["thumbnails"] = thumb_paths

    # Daily Reporter — always runs
    if "report" in active:
        _run_step("Daily Reporter", daily_reporter.run)

    # Dashboard — always runs
    if "dashboard" in active:
        _run_step("Dashboard", dashboard.run)

    elapsed = (datetime.now() - start).seconds
    logger.info(f"{'='*50}")
    logger.info(f"PIPELINE COMPLETE in {elapsed}s")
    logger.info(f"{'='*50}")
    quota_report()


if __name__ == "__main__":
    requested_steps = sys.argv[1:] if len(sys.argv) > 1 else None
    run(requested_steps)
