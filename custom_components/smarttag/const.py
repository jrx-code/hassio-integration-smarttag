"""Stałe integracji SmartTag."""

from datetime import timedelta

DOMAIN = "smarttag"

CONF_TOKEN_SOURCE = "token_source"
CONF_PAT = "pat"
SOURCE_SMARTTHINGS = "smartthings"  # pożycz token OAuth z wbudowanej integracji
SOURCE_PAT = "pat"

CONF_AWAY_SECONDS = "away_seconds"
DEFAULT_AWAY_SECONDS = 300

CLOUD_INTERVAL = timedelta(minutes=30)
PRESENCE_TICK = timedelta(seconds=30)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.pools"

BATTERY_PERCENT = {"FULL": 100, "MEDIUM": 50, "LOW": 15, "VERY_LOW": 5}
