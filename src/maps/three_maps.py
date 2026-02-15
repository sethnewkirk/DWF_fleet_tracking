"""
Three publication-quality maps of China's DWF fleet.

Map 1: Seasonal movement (global, dark theme, 1-deg grid by peak month)
Map 2: Western Hemisphere (light theme, NYT-inspired density + narrative)
Map 3: Indo-Pacific & West Africa (light theme, density + narrative)

Maps 2 & 3 follow NYT visual language: light background, warm effort
density cloud, highlighted affected nations, prose annotations, prominent
EEZ boundaries. The effort layer is background context; the story is told
through narrative text and EEZ positioning.
"""

import sys
from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config
from src.maps.styles import (
    OCEAN_COLOR, LAND_COLOR, COUNTRY_BORDER_COLOR,
    EEZ_LINE_COLOR,
    GRATICULE_COLOR, TEXT_PRIMARY, TEXT_SECONDARY,
    INCIDENT_STYLES,
    FONT_FAMILY, CAVEAT_FONTSIZE,
)

PLATE_CARREE = ccrs.PlateCarree()

# ── Dark theme (Map 1) ───────────────────────────────────────────────────
MONTH_COLORS = {
    1: "#4575b4",  2: "#74add1",  3: "#abd9e9",  4: "#66c2a5",
    5: "#3cb44b",  6: "#fee090",  7: "#fdae61",  8: "#f46d43",
    9: "#d73027",  10: "#a50026", 11: "#8e4585", 12: "#5e4fa2",
}
MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}
TEXT_OUTLINE_DARK = [pe.withStroke(linewidth=3, foreground="#0a1628")]

# ── Light theme (Maps 2 & 3) ─────────────────────────────────────────────
OCEAN_LIGHT = "#f5f5f0"
LAND_LIGHT = "#e5e5dd"
LAND_HIGHLIGHT = "#e5db98"
BORDER_LIGHT = "#c8c8c0"
EEZ_BLUE = "#5bafc8"
TEXT_DARK = "#1a1a1a"
TEXT_BODY = "#3a3a3a"
TEXT_MUTED = "#777777"
EFFORT_WARM = "#cc3300"


# =========================================================================
# Data loading
# =========================================================================

def _load_natural_earth(name: str) -> gpd.GeoDataFrame:
    d = config.NATURAL_EARTH_DIR / name
    shp_files = list(d.glob("*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"No shapefile in {d}")
    return gpd.read_file(shp_files[0])


def _load_eez() -> gpd.GeoDataFrame:
    eez_file = config.EEZ_DIR / "world_eez.geojson"
    if not eez_file.exists():
        raise FileNotFoundError(f"EEZ data not found at {eez_file}")
    return gpd.read_file(eez_file)


def _load_raw_effort(extent=None):
    """Load raw monthly CSVs — gives natural density variation."""
    frames = []
    for year in config.YEARS:
        f = config.GFW_EFFORT_DIR / f"china_effort_{year}.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f)
        df.columns = ["lat", "lon", "time_range", "flag", "geartype",
                      "vessel_count", "fishing_hours"]
        # Exclude domestic
        df = df[~((df["lat"] >= 18) & (df["lat"] <= 42) &
                  (df["lon"] >= 105) & (df["lon"] <= 130))]
        if extent:
            df = df[(df["lon"] >= extent[0]) & (df["lon"] <= extent[1]) &
                    (df["lat"] >= extent[2]) & (df["lat"] <= extent[3])]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# =========================================================================
# Dark theme components (Map 1)
# =========================================================================

def render_dark_basemap(ax):
    """Dark basemap with land, borders, graticules."""
    ax.set_facecolor(OCEAN_COLOR)
    land = _load_natural_earth("land")
    ax.add_geometries(land.geometry, crs=PLATE_CARREE,
                      facecolor=LAND_COLOR, edgecolor=COUNTRY_BORDER_COLOR,
                      linewidth=0.3)
    countries = _load_natural_earth("countries")
    ax.add_geometries(countries.geometry, crs=PLATE_CARREE,
                      facecolor="none", edgecolor=COUNTRY_BORDER_COLOR,
                      linewidth=0.2)
    graticules = _load_natural_earth("graticules")
    ax.add_geometries(graticules.geometry, crs=PLATE_CARREE,
                      facecolor="none", edgecolor=GRATICULE_COLOR,
                      linewidth=0.3)
    ax.set_global()


# =========================================================================
# Light theme components (Maps 2 & 3)
# =========================================================================

def render_light_basemap(ax, extent, highlight_iso=None):
    """
    Light basemap: white ocean, gray land, affected nations highlighted
    in olive/yellow. No graticules — clean like NYT.
    """
    ax.set_facecolor(OCEAN_LIGHT)

    countries = _load_natural_earth("countries")

    # All land in neutral gray
    ax.add_geometries(
        countries.geometry, crs=PLATE_CARREE,
        facecolor=LAND_LIGHT, edgecolor=BORDER_LIGHT, linewidth=0.4,
    )

    # Highlight affected nations in olive/yellow
    if highlight_iso:
        for iso in highlight_iso:
            sel = countries[countries["ADM0_A3"] == iso]
            if len(sel) > 0:
                ax.add_geometries(
                    sel.geometry, crs=PLATE_CARREE,
                    facecolor=LAND_HIGHLIGHT, edgecolor=BORDER_LIGHT,
                    linewidth=0.4,
                )

    ax.set_extent(extent, crs=PLATE_CARREE)


def render_eez_light(ax, highlight_countries=None):
    """EEZ boundaries on light background — light blue, prominent."""
    try:
        eez = _load_eez()
    except FileNotFoundError:
        return

    # All EEZ very subtle
    ax.add_geometries(
        eez.geometry, crs=PLATE_CARREE,
        facecolor="none", edgecolor="#c0d0d8",
        linewidth=0.3, alpha=0.25,
    )

    # Key nations: prominent light blue
    if highlight_countries:
        for iso in highlight_countries:
            sel = eez[eez["ISO_A3"] == iso]
            if len(sel) > 0:
                ax.add_geometries(
                    sel.geometry, crs=PLATE_CARREE,
                    facecolor="none", edgecolor=EEZ_BLUE,
                    linewidth=1.5, alpha=0.7,
                )


def render_effort_density(ax, df, alpha_min=0.04, alpha_max=0.20,
                          point_size=0.6):
    """
    Render effort as a density cloud of semi-transparent warm dots.
    Natural row density (monthly × geartype) creates the heatmap effect.
    Alpha modulated by fishing hours for intensity weighting.
    """
    if len(df) == 0:
        return

    hours = df["fishing_hours"].values
    log_h = np.log1p(hours)
    p95 = np.percentile(log_h, 95)
    if p95 == 0:
        p95 = 1
    norm = np.clip(log_h / p95, 0, 1)
    alphas = alpha_min + (alpha_max - alpha_min) * norm

    rgb = mcolors.to_rgb(EFFORT_WARM)
    colors = np.column_stack([
        np.full(len(df), rgb[0]),
        np.full(len(df), rgb[1]),
        np.full(len(df), rgb[2]),
        alphas,
    ])

    ax.scatter(
        df["lon"].values, df["lat"].values,
        c=colors, s=point_size, edgecolors="none",
        transform=PLATE_CARREE, rasterized=True, zorder=2,
    )


# ── Flow arrows ─────────────────────────────────────────────────────────

def _bezier_quad(p0, p1, p2, n=120):
    """Quadratic Bézier curve. p0=start, p1=control, p2=end."""
    t = np.linspace(0, 1, n)
    x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
    y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
    return x, y


def draw_flow_arrow(ax, start, end, bend=5, color=EFFORT_WARM,
                    alpha=0.55, linewidth=3.0, head_size=120):
    """
    Draw a curved flow arrow on the map from start to end.

    bend: perpendicular offset of the control point from the midpoint.
          Positive = curve left (relative to travel direction),
          negative = curve right.
    """
    mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)

    # Perpendicular direction
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = np.hypot(dx, dy)
    if length == 0:
        return
    nx, ny = -dy / length, dx / length
    ctrl = (mid[0] + nx * bend, mid[1] + ny * bend)

    lons, lats = _bezier_quad(start, ctrl, end, n=120)

    # Draw path
    ax.plot(lons, lats, color=color, alpha=alpha, linewidth=linewidth,
            transform=PLATE_CARREE, zorder=5, solid_capstyle="round")

    # Arrowhead — triangle pointing in direction of travel
    ddx = lons[-1] - lons[-6]
    ddy = lats[-1] - lats[-6]
    angle = np.degrees(np.arctan2(ddy, ddx))
    ax.scatter(
        lons[-1], lats[-1],
        marker=(3, 0, angle - 90),
        s=head_size, color=color, alpha=min(alpha + 0.15, 1.0),
        transform=PLATE_CARREE, zorder=6, edgecolors="none",
    )


def render_incidents_subtle(ax, incidents_df):
    """Small incident markers — no labels, narrative text handles context."""
    if incidents_df is None or len(incidents_df) == 0:
        return
    for _, row in incidents_df.iterrows():
        cat = row["category"]
        style = INCIDENT_STYLES.get(cat, INCIDENT_STYLES["eez_violation"])
        ax.scatter(
            row["lon"], row["lat"],
            c=style["color"], marker=style["marker"],
            s=style["size"] * 0.7,
            edgecolors="white", linewidths=0.8, alpha=0.85,
            transform=PLATE_CARREE, zorder=10,
        )


def add_narrative(ax, lon, lat, text, fontsize=9.5, ha="left", va="top",
                  width=None):
    """NYT-style narrative prose annotation at a geographic position."""
    ax.text(
        lon, lat, text,
        transform=PLATE_CARREE,
        fontsize=fontsize, fontfamily=FONT_FAMILY,
        color=TEXT_BODY, ha=ha, va=va,
        linespacing=1.5,
        bbox=dict(
            boxstyle="square,pad=0.6",
            facecolor="white",
            edgecolor="none",
            alpha=0.88,
        ),
        zorder=15,
    )


def add_country_label(ax, lon, lat, name, fontsize=11):
    """Clean country label in muted gray."""
    ax.text(
        lon, lat, name.upper(),
        transform=PLATE_CARREE,
        fontsize=fontsize, fontfamily=FONT_FAMILY,
        color=TEXT_MUTED, ha="center", va="center",
        fontweight="bold", zorder=6,
    )


def add_eez_label(ax, lon, lat, text, fontsize=8):
    """Label for an EEZ zone in the EEZ blue color."""
    ax.text(
        lon, lat, text,
        transform=PLATE_CARREE,
        fontsize=fontsize, fontfamily=FONT_FAMILY,
        color=EEZ_BLUE, ha="center", va="center",
        style="italic", alpha=0.85, zorder=6,
    )


# =========================================================================
# MAP 1: Seasonal Movement (Global, dark theme)
# =========================================================================

def render_seasonal_map():
    """Global map: 1-deg grid colored by peak fishing month."""
    print("=== Map 1: Seasonal Movement ===")

    effort = _load_raw_effort()
    effort["month"] = effort["time_range"].str[5:7].astype(int)

    # Aggregate to 1-degree grid
    res = 1.0
    effort["grid_lat"] = (effort["lat"] / res).round() * res
    effort["grid_lon"] = (effort["lon"] / res).round() * res

    monthly_grid = effort.groupby(
        ["grid_lat", "grid_lon", "month"], as_index=False
    ).agg(fishing_hours=("fishing_hours", "sum"))

    idx = monthly_grid.groupby(["grid_lat", "grid_lon"])["fishing_hours"].idxmax()
    dominant = monthly_grid.loc[idx].copy()

    totals = effort.groupby(
        ["grid_lat", "grid_lon"]
    )["fishing_hours"].sum().reset_index(name="total_hours")
    dominant = dominant.merge(totals, on=["grid_lat", "grid_lon"])
    print(f"  {len(dominant):,} grid cells at {res}\u00b0 resolution")

    projection = ccrs.Robinson(central_longitude=180)
    fig = plt.figure(figsize=(24, 13), facecolor=OCEAN_COLOR)
    ax = fig.add_subplot(1, 1, 1, projection=projection)

    render_dark_basemap(ax)

    # Render EEZ (dark theme)
    try:
        eez = _load_eez()
        ax.add_geometries(eez.geometry, crs=PLATE_CARREE,
                          facecolor="none", edgecolor=EEZ_LINE_COLOR,
                          linewidth=0.3, alpha=0.12)
    except FileNotFoundError:
        pass

    # Alpha from effort intensity
    log_h = np.log1p(dominant["total_hours"].values)
    p95 = np.percentile(log_h, 95)
    if p95 == 0:
        p95 = 1
    norm = np.clip(log_h / p95, 0, 1)
    alphas = 0.15 + 0.75 * (norm ** 1.2)

    for month in range(1, 13):
        mask = dominant["month"] == month
        if not mask.any():
            continue
        mdata = dominant[mask]
        rgb = mcolors.to_rgb(MONTH_COLORS[month])
        ma = alphas[mask.values]
        colors = np.column_stack([
            np.full(len(mdata), rgb[0]),
            np.full(len(mdata), rgb[1]),
            np.full(len(mdata), rgb[2]),
            ma,
        ])
        ax.scatter(
            mdata["grid_lon"].values, mdata["grid_lat"].values,
            c=colors, s=14, marker="s",
            transform=PLATE_CARREE, rasterized=True, zorder=2,
        )

    # Region labels (dark theme)
    def _label(lon, lat, text, fs=9):
        ax.text(lon, lat, text, transform=PLATE_CARREE,
                fontsize=fs, fontfamily=FONT_FAMILY,
                color=TEXT_SECONDARY, ha="center", va="center",
                style="italic", path_effects=TEXT_OUTLINE_DARK, zorder=8)

    _label(-58, -52, "Patagonian\nShelf", 10)
    _label(-92, -5, "Gal\u00e1pagos", 10)
    _label(-170, -14, "American\nSamoa", 9)
    _label(-155, 24, "Hawai\u02bbi", 9)
    _label(55, -22, "Indian\nOcean", 10)
    _label(-8, 7, "Gulf of\nGuinea", 9)
    _label(152, 38, "N. Pacific\nSquid Grounds", 9)
    _label(125, -8, "SE Asia /\nCoral Triangle", 9)
    _label(127, 37, "Korean\nWaters", 8)

    # Month legend
    month_patches = [
        mpatches.Patch(color=MONTH_COLORS[m], label=MONTH_NAMES[m])
        for m in range(1, 13)
    ]
    leg = ax.legend(
        handles=month_patches, title="Peak Fishing Month",
        loc="lower left", ncol=3,
        fontsize=8, title_fontsize=9,
        facecolor="#0d1b2a", edgecolor="#333355",
        labelcolor=TEXT_PRIMARY, framealpha=0.92,
    )
    leg.get_title().set_color(TEXT_PRIMARY)

    fig.text(0.5, 0.96,
             "China\u2019s Distant Water Fleet: "
             "Seasonal Fishing Patterns 2022\u20132025",
             ha="center", va="top", fontsize=24, fontweight="bold",
             fontfamily=FONT_FAMILY, color=TEXT_PRIMARY)
    fig.text(0.5, 0.935,
             "Each cell colored by peak fishing month  \u2022  "
             "Brightness shows effort intensity  \u2022  1\u00b0 grid",
             ha="center", va="top", fontsize=12,
             fontfamily=FONT_FAMILY, color=TEXT_SECONDARY)
    fig.text(0.02, 0.01,
             "Source: Global Fishing Watch 4Wings API (CC BY-SA 4.0)  "
             "\u2022  Robinson projection centered on 180\u00b0",
             fontsize=CAVEAT_FONTSIZE, fontfamily=FONT_FAMILY,
             color=TEXT_SECONDARY, ha="left", va="bottom")
    fig.text(0.98, 0.01,
             "Note: AIS-broadcasting vessels only (~50% of fleet). "
             "China domestic waters excluded.",
             fontsize=CAVEAT_FONTSIZE, fontfamily=FONT_FAMILY,
             color=TEXT_SECONDARY, ha="right", va="bottom", style="italic")

    config.STATIC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = config.STATIC_OUTPUT_DIR / "map1_seasonal_movement.png"
    fig.savefig(out, dpi=300, bbox_inches="tight",
                facecolor=fig.get_facecolor(), pad_inches=0.4)
    plt.close(fig)
    print(f"  Saved: {out}")


# =========================================================================
# MAP 2: Western Hemisphere (light theme)
# =========================================================================

def render_western_hemisphere_map():
    """Americas: flow arrows showing fleet corridors, Pacific island labels."""
    print("\n=== Map 2: Western Hemisphere ===")

    extent = [-180, -30, -60, 18]

    # Load raw effort for subtle background density
    print("  Loading raw effort data...")
    effort = _load_raw_effort(extent=extent)
    print(f"  {len(effort):,} raw effort rows in extent")

    # Load incidents
    from src.data.process_incidents import load_incidents
    try:
        incidents = load_incidents()
        inc = incidents[
            (incidents["lon"] >= extent[0]) & (incidents["lon"] <= extent[1]) &
            (incidents["lat"] >= extent[2]) & (incidents["lat"] <= extent[3])
        ]
    except FileNotFoundError:
        inc = None

    # ── Render ──
    fig = plt.figure(figsize=(20, 16), facecolor=OCEAN_LIGHT)
    ax = fig.add_subplot(1, 1, 1, projection=PLATE_CARREE)

    # Basemap: highlight South American nations AND Pacific island nations
    render_light_basemap(ax, extent,
                         highlight_iso=["ARG", "ECU", "PER", "CHL"])
    render_eez_light(ax, highlight_countries=[
        "ARG", "ECU", "PER", "CHL",
        "ASM", "WSM", "KIR", "COK", "TON", "PYF", "TKL", "NIU",
    ])

    # Subtle effort density (background context, not the focus)
    print("  Rendering subtle effort density...")
    render_effort_density(ax, effort,
                          alpha_min=0.015, alpha_max=0.07, point_size=0.3)

    # Subtle incident markers
    if inc is not None:
        render_incidents_subtle(ax, inc)

    # ── Flow arrows (primary visual) ──
    print("  Drawing flow arrows...")

    # Route A: Main Pacific entry → equatorial squid belt
    draw_flow_arrow(
        ax, start=(-178, -2), end=(-105, -12),
        bend=6, color=EFFORT_WARM, alpha=0.55, linewidth=4.0, head_size=160,
    )

    # Route B: Equatorial Pacific → Galápagos approach
    draw_flow_arrow(
        ax, start=(-105, -8), end=(-92, -1),
        bend=-3, color=EFFORT_WARM, alpha=0.5, linewidth=3.0, head_size=120,
    )

    # Route C: Eastern Pacific → Patagonian Shelf (squid season)
    draw_flow_arrow(
        ax, start=(-105, -15), end=(-60, -45),
        bend=8, color=EFFORT_WARM, alpha=0.5, linewidth=3.5, head_size=140,
    )

    # Route D: Entry → South Pacific Islands (longline tuna)
    draw_flow_arrow(
        ax, start=(-178, -8), end=(-155, -20),
        bend=4, color=EFFORT_WARM, alpha=0.45, linewidth=2.5, head_size=100,
    )

    # ── Country labels (South America) ──
    add_country_label(ax, -65, -28, "Argentina", fontsize=12)
    add_country_label(ax, -77, -10, "Peru", fontsize=10)
    add_country_label(ax, -72, -34, "Chile", fontsize=9)
    add_country_label(ax, -78, 1, "Ecuador", fontsize=9)

    # ── Pacific island labels ──
    add_country_label(ax, -170, -14, "Samoa", fontsize=7)
    add_country_label(ax, -160, -21, "Cook Is.", fontsize=7)
    add_country_label(ax, -175, -21, "Tonga", fontsize=7)
    add_country_label(ax, -157, -3, "Kiribati", fontsize=7)
    add_country_label(ax, -149, -17, "Fr. Polynesia", fontsize=6)

    # ── EEZ labels ──
    add_eez_label(ax, -88, -7, "Gal\u00e1pagos\nexclusive\neconomic zone")
    add_eez_label(ax, -55, -50, "Argentine EEZ")

    # ── Narrative annotations ──
    add_narrative(
        ax, -178, 13,
        "Arrows show major fleet corridors.\n"
        "Nearly 3,000 Chinese vessels\n"
        "operate worldwide \u2014 the largest\n"
        "distant water fleet in history.\n"
        "Shading shows fishing intensity.",
        fontsize=9, ha="left", va="top",
    )

    add_narrative(
        ax, -82, -13,
        "Each year, hundreds of Chinese\n"
        "vessels fish right at the edge of\n"
        "the Gal\u00e1pagos EEZ. In 2023,\n"
        "510 vessels were documented here,\n"
        "along with 53 AIS shutoff events.",
        fontsize=9.5,
    )

    add_narrative(
        ax, -48, -30,
        "Each squid season, 300\u2013380 Chinese\n"
        "vessels mass along Argentina\u2019s EEZ\n"
        "boundary. The Argentine Navy has\n"
        "repeatedly intercepted boats inside\n"
        "the zone. Chinese vessels account for\n"
        "92% of AIS disabling events here.",
        fontsize=9.5,
    )

    add_narrative(
        ax, -178, -28,
        "Chinese longliners take half the\n"
        "South Pacific albacore catch.\n"
        "Small island nations like Samoa,\n"
        "Tonga, and Kiribati lack the coast\n"
        "guards to patrol their vast EEZs.",
        fontsize=9,
    )

    # ── Title ──
    fig.text(0.08, 0.97,
             "China\u2019s Distant Water Fleet\n"
             "in the Western Hemisphere",
             ha="left", va="top", fontsize=26, fontweight="bold",
             fontfamily=FONT_FAMILY, color=TEXT_DARK)
    fig.text(0.08, 0.915,
             "Fleet corridors 2022\u20132025  |  "
             "Exclusive economic zones  |  "
             "Documented enforcement incidents",
             ha="left", va="top", fontsize=10,
             fontfamily=FONT_FAMILY, color=TEXT_MUTED)

    fig.text(0.02, 0.01,
             "Source: Global Fishing Watch (CC BY-SA 4.0). "
             "EEZ boundaries via Marine Regions. "
             "Incidents from curated open-source reports.",
             fontsize=7, fontfamily=FONT_FAMILY,
             color=TEXT_MUTED, ha="left", va="bottom")

    out = config.STATIC_OUTPUT_DIR / "map2_western_hemisphere.png"
    fig.savefig(out, dpi=300, bbox_inches="tight",
                facecolor=fig.get_facecolor(), pad_inches=0.3)
    plt.close(fig)
    print(f"  Saved: {out}")


# =========================================================================
# MAP 3: Indo-Pacific & West Africa (light theme)
# =========================================================================

def render_indo_pacific_map():
    """Asia-Pacific + West Africa: light theme, density + narrative."""
    print("\n=== Map 3: Indo-Pacific & West Africa ===")

    extent = [-20, 175, -42, 48]

    print("  Loading raw effort data...")
    effort = _load_raw_effort(extent=extent)
    print(f"  {len(effort):,} raw effort rows in extent")

    from src.data.process_incidents import load_incidents
    try:
        incidents = load_incidents()
        inc = incidents[
            (incidents["lon"] >= extent[0]) & (incidents["lon"] <= extent[1]) &
            (incidents["lat"] >= extent[2]) & (incidents["lat"] <= extent[3])
        ]
    except FileNotFoundError:
        inc = None

    # ── Render ──
    fig = plt.figure(figsize=(22, 14), facecolor=OCEAN_LIGHT)
    ax = fig.add_subplot(1, 1, 1, projection=PLATE_CARREE)

    render_light_basemap(ax, extent,
                         highlight_iso=["KOR", "GHA", "CIV", "GIN", "VUT"])
    render_eez_light(ax, highlight_countries=[
        "KOR", "JPN", "PHL", "VNM", "IDN",
        "GHA", "CIV", "GIN", "VUT", "FJI",
    ])

    print("  Rendering effort density cloud...")
    render_effort_density(ax, effort)

    if inc is not None:
        render_incidents_subtle(ax, inc)

    # ── Country labels ──
    add_country_label(ax, 128, 36, "South\nKorea", fontsize=9)
    add_country_label(ax, 105, 18, "Vietnam", fontsize=8)
    add_country_label(ax, 118, 3, "Indonesia", fontsize=9)
    add_country_label(ax, -3, 7, "Ghana", fontsize=8)
    add_country_label(ax, -12, 11, "Guinea", fontsize=8)

    # ── EEZ labels ──
    add_eez_label(ax, 122, 40, "Korean EEZ")
    add_eez_label(ax, 170, -18, "Vanuatu EEZ")

    # ── Narrative annotations ──
    add_narrative(
        ax, 134, 44,
        "South Korean authorities seized\n"
        "dozens of Chinese fishing boats\n"
        "in the Yellow Sea. Crews resisted\n"
        "boarding with iron bars and steel\n"
        "barriers. In one case, boats\n"
        "carried 1-inch mesh nets — the\n"
        "legal minimum is 21 inches.",
        fontsize=9,
    )

    add_narrative(
        ax, -15, -5,
        "90% of Ghana\u2019s industrial trawl\n"
        "fleet is Chinese-owned through\n"
        "front companies, despite laws\n"
        "forbidding foreign ownership.\n"
        "Local artisanal fishers report\n"
        "40% income declines.",
        fontsize=9,
    )

    add_narrative(
        ax, 50, -30,
        "The fleet operates year-round\n"
        "across the Indian Ocean, targeting\n"
        "tuna and squid in some of the\n"
        "world\u2019s least-patrolled waters.",
        fontsize=9,
    )

    add_narrative(
        ax, 148, -30,
        "Six Chinese vessels caught violating\n"
        "catch-recording rules in Vanuatu.\n"
        "The U.S. Coast Guard assisted in\n"
        "boarding operations.",
        fontsize=8.5,
    )

    # ── Title ──
    fig.text(0.06, 0.97,
             "China\u2019s Distant Water Fleet:\n"
             "Indo-Pacific & West Africa",
             ha="left", va="top", fontsize=24, fontweight="bold",
             fontfamily=FONT_FAMILY, color=TEXT_DARK)
    fig.text(0.06, 0.915,
             "Fishing effort 2022\u20132025  |  "
             "Exclusive economic zones  |  "
             "Documented enforcement incidents",
             ha="left", va="top", fontsize=10,
             fontfamily=FONT_FAMILY, color=TEXT_MUTED)

    fig.text(0.02, 0.01,
             "Source: Global Fishing Watch (CC BY-SA 4.0). "
             "EEZ boundaries via Marine Regions. "
             "Incidents from curated open-source reports.",
             fontsize=7, fontfamily=FONT_FAMILY,
             color=TEXT_MUTED, ha="left", va="bottom")

    out = config.STATIC_OUTPUT_DIR / "map3_indo_pacific.png"
    fig.savefig(out, dpi=300, bbox_inches="tight",
                facecolor=fig.get_facecolor(), pad_inches=0.3)
    plt.close(fig)
    print(f"  Saved: {out}")


# =========================================================================

if __name__ == "__main__":
    render_seasonal_map()
    render_western_hemisphere_map()
    render_indo_pacific_map()
    print("\n=== All three maps rendered ===")
