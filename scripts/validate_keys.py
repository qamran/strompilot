"""Prove both model API keys work with minimal live calls.

Reads keys from the project .env file. Prints only statuses, never key
material. Exits 0 only when both provider legs answer successfully.
"""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT_SECONDS = 60.0


def check_chat_completions(label: str, base_url: str, model: str, api_key: str) -> bool:
    """Send one tiny chat completion and report success without logging secrets."""
    url = f"{base_url}/chat/completions"
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with the word OK."}],
                "max_tokens": 10,
            },
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        print(f"{label}: request failed ({type(exc).__name__})")
        return False
    if response.status_code != 200:
        print(f"{label}: HTTP {response.status_code} from {base_url}")
        return False
    try:
        text = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        print(f"{label}: unreadable response body")
        return False
    print(f"{label}: OK (model {model}, received {len(str(text))} chars)")
    return True


def main() -> int:
    load_dotenv(ROOT / ".env")
    meta_key = os.environ.get("META_API_KEY", "")
    baseten_key = os.environ.get("BASETEN_API_KEY", "")
    if not meta_key:
        print("META_API_KEY is missing from .env")
        return 1
    if not baseten_key:
        print("BASETEN_API_KEY is missing from .env")
        return 1
    meta_ok = check_chat_completions(
        "meta", "https://api.meta.ai/v1", "muse-spark-1.3", meta_key
    )
    baseten_ok = check_chat_completions(
        "baseten",
        "https://inference.baseten.co/v1",
        "meta-models/muse-spark-open-1026",
        baseten_key,
    )
    return 0 if (meta_ok and baseten_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
