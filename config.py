"""
Configuration for DWF Fleet Tracking project.

For sensitive values (API keys), set environment variables or create
a config_local.py file (gitignored) that overrides these defaults.
"""

import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent

# Directory structure
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
INCIDENTS_DIR = DATA_DIR / "incidents"
OUTPUT_DIR = PROJECT_ROOT / "output"
STATIC_OUTPUT_DIR = OUTPUT_DIR / "static"
INTERACTIVE_OUTPUT_DIR = OUTPUT_DIR / "interactive"

# Raw data subdirectories
GFW_EFFORT_DIR = RAW_DIR / "gfw_fishing_effort"
GFW_API_DIR = RAW_DIR / "gfw_api"
EEZ_DIR = RAW_DIR / "eez"
NATURAL_EARTH_DIR = RAW_DIR / "natural_earth"

# GFW API configuration
# Set GFW_API_KEY environment variable or override in config_local.py
GFW_API_KEY = os.environ.get("GFW_API_KEY", "")

# GFW data URLs
GFW_ZENODO_BASE = "https://zenodo.org/records/14982712"
GFW_API_BASE = "https://gateway.api.globalfishingwatch.org/v3"

# Natural Earth data URLs (public domain, no registration needed)
NATURAL_EARTH_BASE = "https://naciscdn.org/naturalearth"
NATURAL_EARTH_LAND_URL = f"{NATURAL_EARTH_BASE}/50m/physical/ne_50m_land.zip"
NATURAL_EARTH_OCEAN_URL = f"{NATURAL_EARTH_BASE}/50m/physical/ne_50m_ocean.zip"
NATURAL_EARTH_COASTLINE_URL = f"{NATURAL_EARTH_BASE}/50m/physical/ne_50m_coastline.zip"
NATURAL_EARTH_COUNTRIES_URL = f"{NATURAL_EARTH_BASE}/50m/cultural/ne_50m_admin_0_countries.zip"
NATURAL_EARTH_GRATICULES_URL = f"{NATURAL_EARTH_BASE}/50m/physical/ne_50m_graticules_30.zip"
NATURAL_EARTH_BATHYMETRY_URL = f"{NATURAL_EARTH_BASE}/50m/physical/ne_50m_bathymetry_all.zip"

# Marine Regions EEZ (requires free registration at marineregions.org)
EEZ_DOWNLOAD_URL = "https://www.marineregions.org/download_file.php?name=World_EEZ_v12_20231025.zip"

# Analysis parameters
TARGET_FLAG = "CHN"
YEARS = [2022, 2023, 2024, 2025]
GRID_RESOLUTION = 0.1  # degrees for aggregated effort data

# Map design parameters
MAP_CENTER_LON = 180  # Pacific-centered Robinson projection
MAP_DPI = 300
MAP_WIDTH_INCHES = 26.67  # ~8000px at 300 DPI
MAP_HEIGHT_INCHES = 15.0  # ~4500px at 300 DPI

# Allow local overrides (gitignored)
try:
    from config_local import *  # noqa: F401, F403
except ImportError:
    pass
