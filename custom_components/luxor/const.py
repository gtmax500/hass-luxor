"""Constants for the FX Luminaire Luxor integration."""

from __future__ import annotations

DOMAIN = "luxor"
MANUFACTURER = "FX Luminaire"

# Polling. The controller answers instantly and GroupListGet returns every
# group in one response, so a 30 s poll is negligible load. Polling only
# matters for changes made outside Home Assistant (facepack schedule, app).
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600

# Seconds to wait before confirming state after a command, so several
# commands in a row (e.g. an HA scene touching many groups) share one refresh.
REFRESH_COOLDOWN = 0.5

# Per-request timeout in seconds.
REQUEST_TIMEOUT = 10

# Intensity the controller uses when a light is turned on without a level and
# we have no previous level to restore.
DEFAULT_ON_INTENSITY = 100
