"""Tests for protocol parsing and the API client against a fake controller."""

from __future__ import annotations

import asyncio

import pytest

from conftest import REAL_GROUP_LIST, REAL_THEME_LIST


def run(coro):
    return asyncio.run(coro)


# --- protocol.py -----------------------------------------------------------


def test_parse_real_zd_group_list(luxor):
    groups = luxor.protocol.parse_groups(REAL_GROUP_LIST)
    assert len(groups) == 16
    assert groups[4].name == "Table Overheads"
    assert groups[10].name == "String Lights"
    assert all(g.intensity == 0 for g in groups.values())
    assert groups[1].color is None


def test_parse_zdc_style_fields(luxor):
    # The OpenAPI spec (ZDC) uses Grp/Inten/Colr; the original integration
    # only understood these, which is why it broke on ZD controllers.
    groups = luxor.protocol.parse_groups(
        {"Status": 0, "GroupList": [{"Grp": 7, "Name": "Patio", "Inten": 55, "Colr": 3}]}
    )
    assert groups[7].intensity == 55 and groups[7].color == 3


def test_parse_real_theme_list(luxor):
    themes, restricted = luxor.protocol.parse_themes(REAL_THEME_LIST)
    assert restricted is False
    assert [t.name for t in themes.values()] == ["Evening", "Front Lights", "Hangout", "Bright Deck"]
    assert themes[0].on is True and themes[2].on is False


def test_status_errors(luxor):
    p = luxor.protocol
    assert p.check_status("X", {"Status": 0}) == {"Status": 0}
    with pytest.raises(p.LuxorStatusError, match="theme index out of range"):
        p.check_status("IlluminateTheme", {"Status": 243})
    with pytest.raises(p.LuxorConnectionError):
        p.check_status("X", ["not", "a", "dict"])


@pytest.mark.parametrize(
    ("brightness", "intensity"),
    [(0, 0), (1, 1), (2, 1), (128, 50), (255, 100)],
)
def test_brightness_to_intensity(luxor, brightness, intensity):
    assert luxor.protocol.brightness_to_intensity(brightness) == intensity


def test_intensity_round_trip(luxor):
    p = luxor.protocol
    for i in range(0, 101):
        assert p.brightness_to_intensity(p.intensity_to_brightness(i)) == i


# --- api.py ----------------------------------------------------------------


def test_get_state(client):
    state = run(client.get_state())
    assert state.groups[4].name == "Table Overheads"
    assert state.themes[0].on is True


def test_parameterless_calls_send_no_body(client, controller):
    run(client.controller_name())
    call = client._session.calls[-1]
    assert call["url"] == "http://192.168.60.73/ControllerName.json"
    assert "json" not in call  # same as the curl that worked


def test_illuminate_group_payload_and_effect(client, controller):
    run(client.illuminate_group(10, 40))
    assert controller.requests[-1] == ("IlluminateGroup", {"GroupNumber": 10, "Intensity": 40})
    assert run(client.get_state()).groups[10].intensity == 40


def test_intensity_is_clamped(client, controller):
    run(client.illuminate_group(4, 250))
    assert controller.requests[-1][1]["Intensity"] == 100


def test_theme_on_off(client, controller):
    run(client.illuminate_theme(2, True))
    assert controller.requests[-1] == ("IlluminateTheme", {"ThemeIndex": 2, "OnOff": 1})
    state = run(client.get_state())
    assert state.themes[2].on and state.groups[4].intensity == 60
    run(client.illuminate_theme(2, False))
    state = run(client.get_state())
    assert not state.themes[2].on and state.groups[4].intensity == 0


def test_all_on_all_off(client):
    run(client.illuminate_all())
    assert {g.intensity for g in run(client.get_state()).groups.values()} == {75}
    run(client.extinguish_all())
    state = run(client.get_state())
    assert {g.intensity for g in state.groups.values()} == {0}
    assert not any(t.on for t in state.themes.values())


def test_bad_group_raises_status_error(luxor, client):
    with pytest.raises(luxor.protocol.LuxorStatusError):
        run(client.illuminate_group(99, 50))


def test_retries_one_dropped_connection(client, controller):
    controller.fail_next = 1
    run(client.illuminate_group(4, 30))
    assert controller.groups[4]["Intensity"] == 30


def test_gives_up_after_two_failures(luxor, client, controller):
    controller.fail_next = 2
    with pytest.raises(luxor.protocol.LuxorConnectionError, match="cannot reach"):
        run(client.illuminate_group(4, 30))


def test_concurrent_commands_are_serialized(client, controller):
    async def burst():
        await asyncio.gather(*(client.illuminate_group(n, 10 * n) for n in range(1, 9)))

    run(burst())
    assert [controller.groups[n]["Intensity"] for n in range(1, 9)] == [10 * n for n in range(1, 9)]


def test_host_normalization(luxor):
    c = luxor.api.LuxorClient(None, " http://192.168.60.73/ ")
    assert c.base_url == "http://192.168.60.73"
