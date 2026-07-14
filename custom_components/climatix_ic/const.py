"""Constants for the Climatix IC integration."""

import logging

DOMAIN = "climatix_ic"
LOGGER = logging.getLogger(__package__)

MANUFACTURER = "Siemens"

CONF_TOTP_SECRET = "totp_secret"
CONF_PLANT_ID = "plant_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 120  # seconds; a full poll re-reads every datapoint
MIN_SCAN_INTERVAL = 30
