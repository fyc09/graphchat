from __future__ import annotations

import json
from collections.abc import Generator

import httpx

from .config import LlmConfig


class LlmError(RuntimeError):
    pass


class LlmClient:
    def __init__(self, cfg: LlmConfig) -> None:
        self.cfg = cfg

    def json_completion(self, system_prompt: str, user_prompt: str) -> dict:
        url = f"{self.cfg.base_url}/chat/completions"
        payload = {
            "model": self.cfg.model,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {self.cfg.api_key}"}
        try:
            with httpx.Client(timeout=httpx.Timeout(180.0, connect=20.0)) as client:
                resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as exc:  # noqa: BLE001
            raise LlmError(str(exc)) from exc

    def stream_text_completion(self, system_prompt: str, user_prompt: str) -> Generator[str, None, None]:
        url = f"{self.cfg.base_url}/chat/completions"
        payload = {
            "model": self.cfg.model,
            "temperature": 0.3,
            "stream": True,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.cfg.api_key}",
            "Accept": "text/event-stream",
        }
        try:
            with httpx.Client(timeout=httpx.Timeout(300.0, connect=20.0)) as client:
                with client.stream("POST", url, headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        text = line.strip()
                        if not text.startswith("data:"):
                            continue
                        data_part = text[5:].strip()
                        if data_part == "[DONE]":
                            break
                        chunk = json.loads(data_part)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            yield str(delta)
        except Exception as exc:  # noqa: BLE001
            raise LlmError(str(exc)) from exc
