from __future__ import annotations

import hashlib
import os
from typing import Any

import httpx


class Mem0Adapter:
    """Small replaceable wrapper around Mem0-compatible memory engines."""

    def __init__(self) -> None:
        self.base_url = os.environ.get("MEM0_API_URL", "").rstrip("/")
        self.api_key = os.environ.get("MEM0_API_KEY", "")

    async def add(self, *, memory_id: str, text: str, metadata: dict[str, Any]) -> dict[str, Any]:
        if not self.base_url:
            return {"backend": "fake", "embedding": self.fake_embedding(text), "external_id": memory_id}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{self.base_url}/memories",
                headers=headers,
                json={"id": memory_id, "text": text, "metadata": metadata},
            )
            resp.raise_for_status()
            return resp.json()

    async def search(self, *, query: str, top_k: int, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.base_url:
            return []
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{self.base_url}/memories/search",
                headers=headers,
                json={"query": query, "top_k": top_k, "metadata": metadata},
            )
            resp.raise_for_status()
            body = resp.json()
        if isinstance(body, dict):
            return body.get("results") or body.get("items") or []
        return body if isinstance(body, list) else []

    @staticmethod
    def fake_embedding(text: str, dimensions: int = 64) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        while len(values) < dimensions:
            for byte in digest:
                values.append(round((byte / 255.0) * 2 - 1, 6))
                if len(values) >= dimensions:
                    break
            digest = hashlib.sha256(digest).digest()
        return values

