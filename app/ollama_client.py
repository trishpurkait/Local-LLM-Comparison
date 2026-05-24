from typing import Any, Dict, List, Optional

import httpx

from app.config import OLLAMA_BASE_URL, REQUEST_TIMEOUT


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url.rstrip("/")

    async def list_models(self) -> List[str]:
        url = f"{self.base_url}/api/tags"

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        models = data.get("models", [])

        return [
            model.get("name")
            for model in models
            if model.get("name")
        ]

    async def generate(
        self,
        model: str,
        prompt: str,
        keep_alive: Optional[str | int] = "5m"
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive
        }

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    async def unload_model(self, model: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model,
            "prompt": "",
            "stream": False,
            "keep_alive": 0
        }

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()