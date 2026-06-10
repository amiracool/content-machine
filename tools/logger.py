import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = "content-machine") -> logging.Logger:
    log_dir = Path(".tmp/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)

        ch = logging.StreamHandler(stream=sys.stdout)
        ch.setLevel(logging.INFO)
        # Prevent emoji/unicode in video titles crashing the Windows console
        if hasattr(ch.stream, "reconfigure"):
            try:
                ch.stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger
