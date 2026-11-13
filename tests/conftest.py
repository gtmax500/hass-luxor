"""Test harness for the HA-independent layers (protocol.py, api.py).

Loads custom_components/luxor/{protocol,api,const}.py as a bare package so
Home Assistant isn't needed, and swaps aiohttp for a tiny in-memory stub
that routes POSTs to FakeLuxor.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import sys
import types

import pytest

PKG_DIR = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "luxor"

# Responses captured from a real Luxor ZD (Grant's controller, Nov 2026).
REAL_GROUP_LIST = json.loads(
    '{"Status":0,"GroupList":[{"Name":"Chandelier","GroupNumber":1,"Intensity":0},'
    '{"Name":"Door Lights","GroupNumber":2,"Intensity":0},{"Name":"Post Lights","GroupNumber":3,"Intensity":0},'
    '{"Name":"Table Overheads","GroupNumber":4,"Intensity":0},{"Name":"Grill Lights","GroupNumber":5,"Intensity":0},'
    '{"Name":"Tree Uplights","GroupNumber":6,"Intensity":0},{"Name":"Patio Lights","GroupNumber":7,"Intensity":0},'
    '{"Name":"Steps","GroupNumber":8,"Intensity":0},{"Name":"Dock Lights","GroupNumber":9,"Intensity":0},'
    '{"Name":"String Lights","GroupNumber":10,"Intensity":0},{"Name":"Railing Lights","GroupNumber":11,"Intensity":0},'
    '{"Name":"Beam Lights","GroupNumber":12,"Intensity":0},{"Name":"Trunk Uplight","GroupNumber":13,"Intensity":0},'
    '{"Name":"Wall Light","GroupNumber":14,"Intensity":0},{"Name":"Front Path Lights","GroupNumber":15,"Intensity":0},'
    '{"Name":"Front Uplights","GroupNumber":16,"Intensity":0}]}'
)
REAL_THEME_LIST = json.loads(
    '{"Status":0,"Restricted":0,"ThemeList":[{"Name":"Evening","ThemeIndex":0,"OnOff":1},'
    '{"Name":"Front Lights","ThemeIndex":1,"OnOff":0},{"Name":"Hangout","ThemeIndex":2,"OnOff":0},'
    '{"Name":"Bright Deck","ThemeIndex":3,"OnOff":0}]}'
)


class FakeLuxor:
    """In-memory Luxor ZD following scottlamb/luxor's documented semantics."""

    def __init__(self) -> None:
        self.groups = {g["GroupNumber"]: dict(g) for g in REAL_GROUP_LIST["GroupList"]}
        self.themes = {t["ThemeIndex"]: dict(t) for t in REAL_THEME_LIST["ThemeList"]}
        # Made-up theme contents for tests: Hangout = table 60%, strings 40%.
        self.theme_defs = {2: {4: 60, 10: 40}}
        self.requests: list[tuple[str, object]] = []
        self.fail_next = 0  # number of upcoming requests to drop

    def handle(self, path: str, body: object) -> tuple[int, str]:
        method = path.strip("/").removesuffix(".json")
        self.requests.append((method, body))
        if method == "ControllerName":
            return 200, json.dumps({"Status": 0, "Controller": "luxor"})
        if method == "GroupListGet":
            return 200, json.dumps({"Status": 0, "GroupList": list(self.groups.values())})
        if method == "ThemeListGet":
            return 200, json.dumps(
                {"Status": 0, "Restricted": 0, "ThemeList": list(self.themes.values())}
            )
        if method == "IlluminateGroup":
            n = body["GroupNumber"]
            if n not in self.groups:
                return 200, json.dumps({"Status": 201})
            self.groups[n]["Intensity"] = body["Intensity"]
            return 200, '{"Status":0}'
        if method == "IlluminateTheme":
            i = body["ThemeIndex"]
            if i not in self.themes:
                return 200, json.dumps({"Status": 243})
            on = bool(body["OnOff"])
            self.themes[i]["OnOff"] = int(on)
            for n, level in self.theme_defs.get(i, {}).items():
                self.groups[n]["Intensity"] = level if on else 0
            return 200, '{"Status":0}'
        if method == "IlluminateAll":
            for g in self.groups.values():
                g["Intensity"] = 75
            return 200, '{"Status":0}'
        if method == "ExtinguishAll":
            for g in self.groups.values():
                g["Intensity"] = 0
            for t in self.themes.values():
                t["OnOff"] = 0
            return 200, '{"Status":0}'
        return 200, json.dumps({"Status": 1})


def _make_aiohttp_stub() -> types.ModuleType:
    mod = types.ModuleType("aiohttp")

    class ClientError(Exception):
        pass

    class _Resp:
        def __init__(self, status: int, text: str) -> None:
            self.status = status
            self._text = text

        async def text(self) -> str:
            return self._text

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    class ClientSession:
        def __init__(self, controller: FakeLuxor) -> None:
            self.controller = controller
            self.calls: list[dict] = []

        def post(self, url: str, **kwargs):
            self.calls.append({"url": url, **kwargs})
            if self.controller.fail_next:
                self.controller.fail_next -= 1
                raise ClientError("connection reset")
            path = "/" + url.split("/", 3)[3]
            return _Resp(*self.controller.handle(path, kwargs.get("json")))

    mod.ClientError = ClientError
    mod.ClientSession = ClientSession
    return mod


@pytest.fixture(scope="session")
def luxor():
    """The integration's HA-free modules: luxor.protocol, luxor.api."""
    sys.modules["aiohttp"] = _make_aiohttp_stub()
    pkg = types.ModuleType("luxor_pkg")
    pkg.__path__ = [str(PKG_DIR)]  # skip __init__.py (imports homeassistant)
    sys.modules["luxor_pkg"] = pkg
    return types.SimpleNamespace(
        protocol=importlib.import_module("luxor_pkg.protocol"),
        api=importlib.import_module("luxor_pkg.api"),
        aiohttp=sys.modules["aiohttp"],
    )


@pytest.fixture
def controller() -> FakeLuxor:
    return FakeLuxor()


@pytest.fixture
def client(luxor, controller):
    session = luxor.aiohttp.ClientSession(controller)
    return luxor.api.LuxorClient(session, "192.168.60.73")
