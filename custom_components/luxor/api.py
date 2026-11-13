"""Async client for the Luxor controller's local JSON API."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT
from .protocol import (
    LuxorConnectionError,
    LuxorState,
    check_status,
    clamp_intensity,
    parse_groups,
    parse_themes,
)

_LOGGER = logging.getLogger(__name__)


class LuxorClient:
    """Talks to one Luxor controller.

    Requests are serialized with a lock: the controller is a small embedded
    web server, and HA scenes can otherwise fire many commands at once.
    Every command is idempotent (set a level, set a theme on/off), so a
    dropped connection is retried once.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        self._session = session
        self.host = host.strip().removeprefix("http://").rstrip("/")
        self.base_url = f"http://{self.host}"
        self._timeout = timeout
        self._lock = asyncio.Lock()

    async def _request(
        self, method: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{method}.json"
        # Parameterless calls send no body, exactly like `curl -X POST`.
        kwargs: dict[str, Any] = {} if payload is None else {"json": payload}
        last_err: Exception | None = None
        async with self._lock:
            for attempt in (1, 2):
                try:
                    async with asyncio.timeout(self._timeout):
                        async with self._session.post(url, **kwargs) as resp:
                            if resp.status != 200:
                                raise LuxorConnectionError(
                                    f"{method}: HTTP {resp.status}"
                                )
                            # The controller's Content-Type isn't reliable,
                            # so decode the body ourselves.
                            text = await resp.text()
                    break
                except (aiohttp.ClientError, TimeoutError) as err:
                    last_err = err
                    _LOGGER.debug("%s attempt %s failed: %r", method, attempt, err)
            else:
                raise LuxorConnectionError(
                    f"{method}: cannot reach {self.host}: {last_err!r}"
                ) from last_err
        try:
            data = json.loads(text)
        except ValueError as err:
            raise LuxorConnectionError(f"{method}: invalid JSON {text[:200]!r}") from err
        _LOGGER.debug("%s %s -> %s", method, payload, data)
        return check_status(method, data)

    async def controller_name(self) -> str:
        data = await self._request("ControllerName")
        return str(data.get("Controller") or "Luxor").strip() or "Luxor"

    async def get_state(self) -> LuxorState:
        groups = parse_groups(await self._request("GroupListGet"))
        themes, restricted = parse_themes(await self._request("ThemeListGet"))
        return LuxorState(groups=groups, themes=themes, themes_restricted=restricted)

    async def illuminate_group(self, group_number: int, intensity: int) -> None:
        await self._request(
            "IlluminateGroup",
            {"GroupNumber": int(group_number), "Intensity": clamp_intensity(intensity)},
        )

    async def illuminate_theme(self, theme_index: int, on: bool) -> None:
        await self._request(
            "IlluminateTheme", {"ThemeIndex": int(theme_index), "OnOff": 1 if on else 0}
        )

    async def illuminate_all(self) -> None:
        """All groups to 75% (controller-defined)."""
        await self._request("IlluminateAll")

    async def extinguish_all(self) -> None:
        """All groups to 0% and all themes off."""
        await self._request("ExtinguishAll")
