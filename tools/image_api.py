import base64
import os
import requests
from pathlib import Path
from openai import OpenAI
from tools.logger import setup_logger
from tools.retry import retry
from tools.quota_tracker import increment, check_limit

logger = setup_logger("image_api")

# gpt-image-1 is OpenAI's current image model (dall-e-3 deprecated in SDK v2)
IMAGE_MODEL = "gpt-image-1"
# gpt-image-1 landscape size (dall-e-3 used 1792x1024, gpt-image-1 uses 1536x1024)
DEFAULT_SIZE = "1536x1024"


def _client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set in environment")
    return OpenAI(api_key=key)


@retry(max_attempts=3, base_delay=3.0)
def generate_thumbnail(
    prompt: str,
    output_path: Path,
    size: str = DEFAULT_SIZE,
) -> Path:
    if not check_limit("openai"):
        raise RuntimeError("OpenAI daily image limit reached")

    client = _client()
    logger.info(f"Generating thumbnail ({size}): {prompt[:80]}...")

    resp = client.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        n=1,
        size=size,
    )
    increment("openai")

    image_data: bytes
    item = resp.data[0]

    if getattr(item, "b64_json", None):
        image_data = base64.b64decode(item.b64_json)
    elif getattr(item, "url", None):
        image_data = requests.get(item.url, timeout=30).content
    else:
        raise RuntimeError(f"No image data in response: {item}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_data)
    logger.info(f"Thumbnail saved: {output_path}")
    return output_path
