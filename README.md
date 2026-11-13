# FX Luminaire Luxor for Home Assistant

[![hacs][hacsbadge]][hacs]

Local control of [FX Luminaire Luxor][luxor] landscape lighting controllers
(ZD; ZDC brightness only) from Home Assistant. Talks directly to the
controller's built-in JSON API on your LAN, with no cloud and no Luxor app.

Fork of [dcramer/hass-luxor](https://github.com/dcramer/hass-luxor), rewritten.
Protocol details come from [scottlamb/luxor](https://github.com/scottlamb/luxor)
and [dcramer/luxor-openapi](https://github.com/dcramer/luxor-openapi).

## What you get

All entities belong to one device, the controller:

| Entity | Luxor concept | Notes |
|---|---|---|
| `light.*` per group | Group | Brightness 1–100%. Plain "on" restores the last level. |
| `switch.*_theme_*` per theme | Theme | On = run the theme. Off = the theme's groups go to 0%. |
| `button.*_all_lights_on` | Illuminate All | Every group to 75% (controller default) |
| `button.*_all_lights_off` | Extinguish All | Every group to 0%, all themes off |

Groups and themes you add later in the Luxor app appear automatically.

## Polling

The controller has no push or event API, so state is polled. That's cheap:
`GroupListGet` returns every group in one tiny response.

* **Changes from HA** update the UI right away and are confirmed with a
  refresh 0.5 s later.
* **Changes made outside HA** (facepack schedule, Luxor app, facepack
  buttons) appear within the poll interval. The default is 30 s; change it
  under *Configure*.
* To pick up a scheduled theme change immediately, call
  `homeassistant.update_entity` on any Luxor entity right after the
  scheduled time.

A theme switch's state is the controller's own flag: it reflects the last
theme command. Dimming one group afterwards does not turn the theme switch off.

## Install

**HACS:** HACS → ⋮ → Custom repositories → add this repo's URL as an
*Integration* → install **FX Luminaire Luxor** → restart HA.

**Manual:** copy `custom_components/luxor` into your HA `config/custom_components/`
folder and restart.

Then go to **Settings → Devices & services → Add integration → FX Luminaire Luxor**
and enter the controller's IP. Give the controller a DHCP reservation first.
If its IP changes later, use **Reconfigure** on the integration; your entities
are kept. Home Assistant must be able to reach the controller on TCP port 80.

Quick check from any machine on the LAN:

```sh
curl -X POST http://<controller-ip>/GroupListGet.json
```

## Upgrading from dcramer/hass-luxor

Existing entries are migrated automatically. Group lights keep their entity
IDs. The old theme `scene` entities are replaced by `switch` entities; delete
the leftover scenes and any stale per-group devices by hand.

## Development

```sh
pytest tests   # protocol + client tests, no Home Assistant install needed
```

The tests replay real ZD controller responses against an in-memory fake controller.

[luxor]: https://www.fxl.com/luxor
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
