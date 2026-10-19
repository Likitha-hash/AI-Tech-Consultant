"""Client for Task 1. Task 3 never imports Task 1 code; it only uses the HTTP API."""
import httpx

from . import config


async def ask(question: str) -> dict:
    headers = {"X-API-Key": config.BRAIN_API_KEY} if config.BRAIN_API_KEY else {}
    async with httpx.AsyncClient(timeout=60) as c:
        for attempt in range(3):
            try:
                r = await c.post(f"{config.BRAIN_URL}/ask", json={"question": question[:900]}, headers=headers)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError:
                if attempt == 2:
                    return {"answer": "Knowledge Brain unavailable", "confident": False, "sources": []}
    return {}
