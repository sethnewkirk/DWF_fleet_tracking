"""
Color palettes, fonts, and styling constants for DWF fleet maps.

All colors specified as hex strings. Opacity values are 0.0-1.0.
"""

# =============================================================================
# Base map colors
# =============================================================================

OCEAN_COLOR = "#0a1628"
LAND_COLOR = "#1a1a2e"
COUNTRY_BORDER_COLOR = "#333355"
EEZ_LINE_COLOR = "#4488aa"
EEZ_LINE_ALPHA = 0.20
GRATICULE_COLOR = "#1a2a3a"
TEXT_PRIMARY = "#e0e0e0"
TEXT_SECONDARY = "#888899"

# =============================================================================
# Year color ramp (sequential: pale yellow -> deep crimson)
# =============================================================================

YEAR_COLORS = {
    2022: "#ffffb2",  # Pale yellow
    2023: "#fecc5c",  # Light orange
    2024: "#fd8d3c",  # Orange-red
    2025: "#bd0026",  # Deep crimson
}

YEAR_LABELS = {
    2022: "2022",
    2023: "2023",
    2024: "2024",
    2025: "2025",
}

# =============================================================================
# Incident category styling
# =============================================================================

INCIDENT_STYLES = {
    "eez_violation": {
        "color": "#ff4444",
        "marker": "^",  # triangle
        "label": "EEZ Violation",
        "size": 120,
    },
    "coast_guard_clash": {
        "color": "#ff0000",
        "marker": "D",  # diamond
        "label": "Enforcement Clash",
        "size": 130,
    },
    "ais_disable": {
        "color": "#00ffff",
        "marker": "o",  # circle
        "label": "AIS Disabling Zone",
        "size": 100,
    },
    "ocean_mapping": {
        "color": "#44aaff",
        "marker": "s",  # square
        "label": "Ocean Mapping Behavior",
        "size": 110,
    },
    "us_interest": {
        "color": "#ffd700",
        "marker": "*",  # star
        "label": "U.S. Interest Area",
        "size": 200,
    },
    "transshipment": {
        "color": "#aa66cc",
        "marker": "h",  # hexagon
        "label": "Transshipment",
        "size": 110,
    },
}

# =============================================================================
# Fishing effort heatmap
# =============================================================================

# Opacity range for effort intensity scaling
EFFORT_ALPHA_MIN = 0.05
EFFORT_ALPHA_MAX = 0.70
EFFORT_POINT_SIZE = 0.4

# =============================================================================
# Typography
# =============================================================================

FONT_FAMILY = "sans-serif"
TITLE_FONTSIZE = 28
SUBTITLE_FONTSIZE = 14
LABEL_FONTSIZE = 9
LEGEND_FONTSIZE = 10
ANNOTATION_FONTSIZE = 8
CAVEAT_FONTSIZE = 7

# =============================================================================
# Map layout
# =============================================================================

# Main map
MAP_DPI = 300
MAP_FIGSIZE = (26.67, 15.0)  # inches -> ~8000x4500 px at 300 DPI

# Inset maps (position as [left, bottom, width, height] in figure coords)
INSET_GALAPAGOS = [0.72, 0.55, 0.22, 0.30]
INSET_ARGENTINA = [0.72, 0.12, 0.22, 0.35]
INSET_SAMOA = [0.05, 0.05, 0.20, 0.25]

# =============================================================================
# Interactive map (Leaflet)
# =============================================================================

LEAFLET_TILE_URL = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
LEAFLET_TILE_ATTR = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
    'contributors &copy; <a href="https://carto.com/">CARTO</a>'
)
LEAFLET_INITIAL_ZOOM = 3
LEAFLET_INITIAL_CENTER = [0, 180]  # Pacific-centered
