"""Thin wrapper around OpenAI-compatible chat completion APIs.

Supports DeepSeek Pro, OpenAI, and any provider that speaks the
OpenAI chat-completions protocol. The user provides base_url + api_key.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

DEFAULT_EVAL_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com"


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class CompletionResult:
    model: str
    prompt_messages: List[ChatMessage]
    response_text: str
    usage: Dict[str, int] = field(default_factory=dict)


def _get_api_key(api_key: Optional[str] = None) -> str:
    key = api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "未找到 API key。请设置环境变量 DEEPSEEK_API_KEY 或 OPENAI_API_KEY，"
            "或通过 --api-key 参数传入。"
        )
    return key


def chat_completion(
    user_prompt: str,
    system_prompt: Optional[str] = None,
    model: str = DEFAULT_EVAL_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> CompletionResult:
    """Call an OpenAI-compatible chat completions endpoint.

    Uses stdlib urllib so we don't add a hard dependency on openai/httpx.
    """
    import urllib.request
    import urllib.error

    resolved_key = _get_api_key(api_key)

    messages: List[ChatMessage] = []
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    messages.append(ChatMessage(role="user", content=user_prompt))

    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {resolved_key}",
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(
            f"API 请求失败 ({exc.code}): {error_body[:500]}"
        ) from exc

    choice = body["choices"][0]
    response_text = choice["message"]["content"]
    usage = body.get("usage", {})

    return CompletionResult(
        model=model,
        prompt_messages=messages,
        response_text=response_text,
        usage=usage,
    )
