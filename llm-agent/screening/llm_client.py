"""Thin wrapper around an OpenAI-compatible chat endpoint (defaults to the
project's local Ollama instance, see ../../config.yaml).

No `openai` package dependency — plain requests against /v1/chat/completions.
Override LLM_BASE_URL / LLM_MODEL to point this at a different endpoint
(e.g. someone else's machine, a hosted model) without touching code — this
matters once this runs outside the original dev box (other backend/frontend
devs won't have this exact local Ollama instance).
"""
import json
import os
import time

import requests

BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:11500/v1")
MODEL = os.environ.get("LLM_MODEL", "qwen2.5-7b-instruct-local")


class LLMClient:
    def __init__(self):
        self.total_calls = 0
        self.total_tokens = 0
        self.total_seconds = 0.0

    def chat_json(self, system, user, max_tokens=400, temperature=0.2):
        """Call the model, expect a JSON object back. Returns (parsed_dict, raw_text)."""
        t0 = time.time()
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        self.total_calls += 1
        self.total_tokens += data.get("usage", {}).get("total_tokens", 0)
        self.total_seconds += time.time() - t0

        text = data["choices"][0]["message"]["content"]
        parsed = _extract_json(text)
        return parsed, text


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return None
