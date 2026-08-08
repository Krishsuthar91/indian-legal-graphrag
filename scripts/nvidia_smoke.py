"""Manual NVIDIA NIM smoke test.

Runs ONE real completion against the configured NVIDIA endpoint using the
active provider settings (which may be overridden with env vars). This script
is NOT collected by pytest — it makes a live API call, so run it by hand:

    python scripts/nvidia_smoke.py

It never prints the API key — only its configured state and masked form. The
single request uses a short read timeout and no retries, so it fails fast.
Exit code is 0 on success, 1 on any failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx  # noqa: E402

from src.config.settings import settings  # noqa: E402
from src.llm.llm import get_llm_client  # noqa: E402

SMOKE_TIMEOUT_SECONDS = 30.0


def _masked(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


def _sanitize(text: str, key: str) -> str:
    if key:
        text = text.replace(key, "***")
    return text


def main() -> int:
    client = get_llm_client()
    api_key = getattr(client, "api_key", "") or ""
    print("NVIDIA smoke test")
    print(f"  provider      : {settings.LLM_PROVIDER}")
    print(f"  model         : {client.model}")
    print(f"  base_url      : {getattr(client, 'base_url', 'N/A')}")
    print(f"  api_key       : configured={bool(api_key)} masked={_masked(api_key)}")
    print(f"  request       : single completion, no retries, "
          f"{SMOKE_TIMEOUT_SECONDS:.0f}s read timeout")

    url = f"{client.base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": client.model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Answer in one sentence.",
            },
            {"role": "user", "content": "Hello! Reply with the single word: ok"},
        ],
        "temperature": 0.2,
        "max_tokens": 8,
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(
            SMOKE_TIMEOUT_SECONDS,
            connect=min(10.0, SMOKE_TIMEOUT_SECONDS),
            read=SMOKE_TIMEOUT_SECONDS,
            write=SMOKE_TIMEOUT_SECONDS,
            pool=SMOKE_TIMEOUT_SECONDS,
        )) as http:
            resp = http.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    body_text = resp.text
    print(f"  status        : {resp.status_code}")
    if resp.status_code != 200:
        print(f"  response      : {_sanitize(body_text[:1500], api_key)!r}")
        print("FAILED — NVIDIA endpoint returned a non-2xx status.", file=sys.stderr)
        return 1

    try:
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        print(f"FAILED: response did not contain a completion: {exc}", file=sys.stderr)
        return 1

    print(f"  reply         : {_sanitize(reply, api_key)!r}")
    print("OK — NVIDIA completion succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
