import os
import anthropic
from tools.logger import setup_logger
from tools.retry import retry
from tools.quota_tracker import increment

logger = setup_logger("llm_api")

DEFAULT_MODEL = "claude-opus-4-8"


def _client() -> anthropic.Anthropic:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment")
    return anthropic.Anthropic(api_key=key)


@retry(
    max_attempts=3,
    base_delay=2.0,
    exceptions=(anthropic.APIError, anthropic.RateLimitError, anthropic.APIConnectionError),
)
def complete(
    prompt: str,
    system: str = "",
    max_tokens: int = 4096,
    model: str = DEFAULT_MODEL,
) -> str:
    client = _client()
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    resp = client.messages.create(**kwargs)
    increment("anthropic")

    text = resp.content[0].text
    logger.debug(
        f"Claude response: {len(text)} chars | "
        f"tokens in={resp.usage.input_tokens} out={resp.usage.output_tokens}"
    )
    return text


def analyze(context: str, instruction: str, max_tokens: int = 2048) -> str:
    return complete(
        prompt=f"{context}\n\n---\n\n{instruction}",
        max_tokens=max_tokens,
    )
