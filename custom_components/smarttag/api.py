"""Asynchroniczny klient API SmartThings (aiohttp)."""

from __future__ import annotations

from typing import Any

import aiohttp

from .cloud import API_BASE, is_tag


class SmartTagAuthError(Exception):
    """Token odrzucony (401/403)."""


class SmartTagApiError(Exception):
    """Inny błąd API."""


class SmartThingsClient:
    """Minimalny klient: lista urządzeń i opis urządzenia."""

    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        self._session = session
        self._token = token

    async def _get(self, url: str) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        try:
            async with self._session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as res:
                if res.status in (401, 403):
                    raise SmartTagAuthError(f"HTTP {res.status}")
                if res.status != 200:
                    raise SmartTagApiError(f"HTTP {res.status} dla {url}")
                return await res.json()
        except aiohttp.ClientError as err:
            raise SmartTagApiError(str(err)) from err

    async def async_list_tags(self) -> list[dict[str, Any]]:
        """Zwraca pełne opisy (z bleD2D) wszystkich tagów."""
        url: str | None = f"{API_BASE}/devices"
        tags: list[dict[str, Any]] = []
        while url:
            data = await self._get(url)
            tags.extend(d for d in data.get("items", []) if is_tag(d))
            url = ((data.get("_links") or {}).get("next") or {}).get("href")
        detailed = []
        for dev in tags:
            detailed.append(await self._get(f"{API_BASE}/devices/{dev['deviceId']}"))
        return detailed
