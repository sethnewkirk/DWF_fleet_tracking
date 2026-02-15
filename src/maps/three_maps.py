"""
Three publication-quality maps of China's DWF fleet:
  1. Seasonal movement (global, monthly color cycle)
  2. Western Hemisphere (Americas + Hawaii)
  3. Western Pacific / Indo-Pacific

Each map includes EEZ boundaries, incident annotations, and regional labels.
"""

import sys
from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config
from src.maps.styles import (
    OCEAN_COLOR, LAND_COLOR, COUNTRY_BORDER_COLOR,
    EEZ_LINE_COLOR, EEZ_LINE_ALPHA,
    GRATICULE_COLOR, TEXT_PRIMARY, TEXT_SECONDARY,
    INCIDENT_STYLES,
    FONT_FAMILY, CAVEAT_FONTSIZE,
)

PLATE_CARREE = ccrs.PlateCarree()

# Month color ramp: cool blue (winter) -> warm green (spring) -> hot (summer) -> cool (fall)
MONTH_COLORS = {
    1: "#4575b4",   # Jan - deep blue
    2: "#74add1",   # Feb - light blue
    3: "#abd9e9",   # Mar - pale cyan
    4: "#66c2a5",   # Apr - teal
    5: "#3cb44b",   # May - green
    6: "#fee090",   # Jun - pale gold
    7: "#fdae61",   # Jul - orange
    8: "#f46d43",   # Aug - red-orange
    9: "#d73027",   # Sep - red
    10: "#a50026",  # Oct - crimson
    11: "#8e4585",  # Nov - purple
    12: "#5e4fa2",  # Dec - indigo
}

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

# Text outline for labels over dark backgrounds
TEXT_OUTLINE = [pe.withStroke(linewidth=2.5, foreground="#0a1628")]


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


def render_basemap(ax, extent=None):
    """Render dark basemap with land, borders, graticules."""
    ax.set_facecolor(OCEAN_COLOR)

    land = _load_natural_earth("land")
    ax.add_geometries(
        land.geometry, crs=PLATE_CARREE,
        facecolor=LAND_COLOR, edgecolor=COUNTRY_BORDER_COLOR, linewidth=0.3,
    )
    countries = _load_natural_earth("countries")
    ax.add_geometries(
        countries.geometry, crs=PLATE_CARREE,
        facecolor="none", edgecolor=COUNTRY_BORDER_COLOR, linewidth=0.2,
    )
    graticules = _load_natural_earth("graticules")
    ax.add_geometries(
        graticules.geometry, crs=PLATE_CARREE,
        facecolor="none", edgecolor=GRATICULE_COLOR, linewidth=0.3,
    )

    if extent:
        ax.set_extent(extent, crs=PLATE_CARREE)
    else:
        ax.set_global()


def render_eez(ax, eez_gdf=None, highlight_countries=None):
    """Render EEZ boundaries. Optionally highlight specific countries."""
    if eez_gdf is None:
        try:
            eez_gdf = _load_eez()
        except FileNotFoundError:
            return

    # Draw all EEZ as subtle lines
    ax.add_geometries(
        eez_gdf.geometry, crs=PLATE_CARREE,
        facecolor="none", edgecolor=EEZ_LINE_COLOR,
        linewidth=0.5, alpha=EEZ_LINE_ALPHA + 0.1,
    )

    # Highlight specific countries' EEZ
    if highlight_countries:
        for iso in highlight_countries:
            country_eez = eez_gdf[eez_gdf["ISO_A3"] == iso]
            if len(country_eez) > 0:
                ax.add_geometries(
                    country_eez.geometry, crs=PLATE_CARREE,
                    facecolor="none", edgecolor="#55aadd",
                    linewidth=1.2, alpha=0.5, linestyle="--",
                )


def render_incidents_annotated(ax, incidents_df, projection=None):
    """Render incidents with callout labels, staggering offsets for clusters."""
    if incidents_df is None or len(incidents_df) == 0:
        return

    # Track placed label positions to stagger overlapping annotations
    placed = []

    for idx, (_, row) in enumerate(incidents_df.iterrows()):
        cat = row["category"]
        style = INCIDENT_STYLES.get(cat, INCIDENT_STYLES["eez_violation"])

        ax.scatter(
            row["lon"], row["lat"],
            c=style["color"], marker=style["marker"],
            s=style["size"], edgecolors="white", linewidths=1.2,
            transform=PLATE_CARREE, zorder=10,
        )

        # Short label from title
        label = row.get("title", "")
        if len(label) > 40:
            label = label[:37] + "..."

        # Stagger offset direction to avoid overlapping labels in clusters
        angles = [(14, 12), (-14, 14), (14, -16), (-14, -14),
                  (20, 0), (-20, 0), (0, 20), (0, -20)]
        offset = angles[idx % len(angles)]

        # Check proximity to already-placed labels and adjust
        for (px, py) in placed:
            if abs(row["lon"] - px) < 3 and abs(row["lat"] - py) < 3:
                offset = angles[(idx + 2) % len(angles)]
                break
        placed.append((row["lon"], row["lat"]))

        ax.annotate(
            label,
            xy=(row["lon"], row["lat"]),
            xytext=offset,
            textcoords="offset points",
            fontsize=5.5,
            fontfamily=FONT_FAMILY,
            color=TEXT_PRIMARY,
            path_effects=TEXT_OUTLINE,
            xycoords=PLATE_CARREE._as_mpl_transform(ax),
            zorder=11,
            arrowprops=dict(
                arrowstyle="-",
                color="#666688",
                linewidth=0.5,
            ),
        )


def add_region_label(ax, lon, lat, text, fontsize=8, color=TEXT_SECONDARY):
    """Add a region label with text outline for readability."""
    ax.text(
        lon, lat, text,
        transform=PLATE_CARREE,
        fontsize=fontsize, fontfamily=FONT_FAMILY,
        color=color, ha="center", va="center",
        style="italic",
        path_effects=TEXT_OUTLINE,
        zorder=8,
    )


# =========================================================================
# MAP 1: Seasonal Movement (Global)
# =========================================================================

def render_seasonal_map():
    """Global map showing fleet movement patterns by month."""
    print("=== Map 1: Seasonal Movement ===")

    # Load raw data with monthly resolution
    frames = []
    for year in config.YEARS:
        f = config.GFW_EFFORT_DIR / f"china_effort_{year}.csv"
        if f.exists():
            df = pd.read_csv(f)
            df.columns = ["lat", "lon", "time_range", "flag", "geartype",
                          "vessel_count", "fishing_hours"]
            # Exclude domestic
            df = df[~((df["lat"] >= 18) & (df["lat"] <= 42) &
                      (df["lon"] >= 105) & (df["lon"] <= 130))]
            df["month"] = df["time_range"].str[5:7].astype(int)
            frames.append(df)

    effort = pd.concat(frames, ignore_index=True)

    # Aggregate by cell + month (across all years for cleaner patterns)
    monthly = effort.groupby(["lat", "lon", "month"], as_index=False).agg(
        fishing_hours=("fishing_hours", "sum"),
    )
    print(f"  {len(monthly):,} cells with monthly data")

    # Determine dominant month per cell (where most fishing hours occur)
    dominant = effort.groupby(["lat", "lon", "month"], as_index=False).agg(
        fishing_hours=("fishing_hours", "sum"),
    )
    idx = dominant.groupby(["lat", "lon"])["fishing_hours"].idxmax()
    dominant = dominant.loc[idx].copy()
    total_per_cell = effort.groupby(["lat", "lon"])["fishing_hours"].sum().reset_index()
    total_per_cell.columns = ["lat", "lon", "total_hours"]
    dominant = dominant.merge(total_per_cell, on=["lat", "lon"])
    print(f"  {len(dominant):,} unique cells with dominant month")

    # Render
    projection = ccrs.Robinson(central_longitude=180)
    fig = plt.figure(figsize=(24, 13), facecolor=OCEAN_COLOR)
    ax = fig.add_subplot(1, 1, 1, projection=projection)

    render_basemap(ax)
    render_eez(ax)

    # Plot each cell colored by dominant month, alpha by total effort
    log_hours = np.log1p(dominant["total_hours"].values)
    p95 = np.percentile(log_hours, 95)
    if p95 == 0:
        p95 = 1
    normalized = np.clip(log_hours / p95, 0, 1)
    alphas = 0.08 + 0.65 * (normalized ** 1.5)

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
            mdata["lon"].values, mdata["lat"].values,
            c=colors, s=0.5, transform=PLATE_CARREE,
            rasterized=True, zorder=2,
        )

    # Region labels
    add_region_label(ax, -58, -48, "Argentine\nShelf", fontsize=9)
    add_region_label(ax, -90, -2, "Galapagos", fontsize=9)
    add_region_label(ax, -170, -12, "American\nSamoa", fontsize=8)
    add_region_label(ax, -155, 22, "Hawaii", fontsize=8)
    add_region_label(ax, 55, -20, "Indian\nOcean", fontsize=9)
    add_region_label(ax, -5, 5, "West\nAfrica", fontsize=9)
    add_region_label(ax, 155, 35, "N. Pacific\nSquid Grounds", fontsize=8)
    add_region_label(ax, 130, -5, "SE Asia", fontsize=8)

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
        labelcolor=TEXT_PRIMARY, framealpha=0.9,
    )
    leg.get_title().set_color(TEXT_PRIMARY)

    # Title
    fig.text(
        0.5, 0.95,
        "China\u2019s Distant Water Fleet: Seasonal Fishing Patterns 2022\u20132025",
        ha="center", va="top", fontsize=24, fontweight="bold",
        fontfamily=FONT_FAMILY, color=TEXT_PRIMARY,
    )
    fig.text(
        0.5, 0.925,
        "Each cell colored by its peak fishing month  \u2022  Brightness indicates total effort intensity",
        ha="center", va="top", fontsize=12,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY,
    )
    fig.text(
        0.02, 0.01,
        "Source: Global Fishing Watch 4Wings API (CC BY-SA 4.0)  \u2022  Robinson projection centered on 180\u00b0",
        ha="left", va="bottom", fontsize=CAVEAT_FONTSIZE,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY,
    )
    fig.text(
        0.98, 0.01,
        "Note: Only AIS-broadcasting vessels shown (~50% of fleet). "
        "Domestic waters (China EEZ) excluded.",
        ha="right", va="bottom", fontsize=CAVEAT_FONTSIZE,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY, style="italic",
    )

    config.STATIC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = config.STATIC_OUTPUT_DIR / "map1_seasonal_movement.png"
    fig.savefig(out, dpi=300, bbox_inches="tight",
                facecolor=fig.get_facecolor(), pad_inches=0.4)
    plt.close(fig)
    print(f"  Saved: {out}")


# =========================================================================
# MAP 2: Western Hemisphere
# =========================================================================

def render_western_hemisphere_map():
    """Americas-focused map: Argentina, Galapagos, American Samoa, Hawaii."""
    print("\n=== Map 2: Western Hemisphere ===")

    effort = pd.read_parquet(config.PROCESSED_DIR / "china_dwf_effort.parquet")
    gaps = None
    gap_path = config.PROCESSED_DIR / "ais_gaps_intentional.parquet"
    if gap_path.exists():
        gaps = pd.read_parquet(gap_path)

    from src.data.process_incidents import load_incidents
    try:
        incidents = load_incidents()
    except FileNotFoundError:
        incidents = None

    # Filter to Western Hemisphere extent
    # Use -180 to -30 longitude (Americas + eastern Pacific), lat to 35 to include Hawaii
    extent = [-180, -30, -60, 35]
    effort_wh = effort[(effort["lon"] >= extent[0]) & (effort["lon"] <= extent[1]) &
                       (effort["lat"] >= extent[2]) & (effort["lat"] <= extent[3])]
    print(f"  Effort cells in view: {len(effort_wh):,}")

    if incidents is not None:
        inc_wh = incidents[(incidents["lon"] >= extent[0]) & (incidents["lon"] <= extent[1]) &
                          (incidents["lat"] >= extent[2]) & (incidents["lat"] <= extent[3])]
    else:
        inc_wh = None

    if gaps is not None:
        gaps_wh = gaps[(gaps["off_lon"] >= extent[0]) & (gaps["off_lon"] <= extent[1]) &
                       (gaps["off_lat"] >= extent[2]) & (gaps["off_lat"] <= extent[3])]
    else:
        gaps_wh = None

    # Render
    fig = plt.figure(figsize=(20, 16), facecolor=OCEAN_COLOR)
    ax = fig.add_subplot(1, 1, 1, projection=PLATE_CARREE)

    render_basemap(ax, extent=extent)
    render_eez(ax, highlight_countries=["ARG", "ECU", "USA", "PER", "CHL", "BRA"])

    # Effort by year
    from src.maps.styles import YEAR_COLORS, EFFORT_ALPHA_MIN, EFFORT_ALPHA_MAX
    for year in sorted(effort_wh["year"].unique()):
        if year not in YEAR_COLORS:
            continue
        yd = effort_wh[effort_wh["year"] == year]
        hours = yd["fishing_hours"].values
        log_h = np.log1p(hours)
        p95 = np.percentile(log_h, 95) if len(log_h) > 0 else 1
        if p95 == 0:
            p95 = 1
        norm = np.clip(log_h / p95, 0, 1)
        alphas = EFFORT_ALPHA_MIN + (EFFORT_ALPHA_MAX - EFFORT_ALPHA_MIN) * (norm ** 2)
        rgb = mcolors.to_rgb(YEAR_COLORS[year])
        colors = np.column_stack([
            np.full(len(yd), rgb[0]), np.full(len(yd), rgb[1]),
            np.full(len(yd), rgb[2]), alphas,
        ])
        ax.scatter(
            yd["lon"].values, yd["lat"].values,
            c=colors, s=0.8, transform=PLATE_CARREE,
            rasterized=True, zorder=2,
        )

    # AIS gaps
    if gaps_wh is not None and len(gaps_wh) > 0:
        ax.scatter(
            gaps_wh["off_lon"].values, gaps_wh["off_lat"].values,
            c="#88ccff", s=4, alpha=0.2,
            transform=PLATE_CARREE, rasterized=True, zorder=3,
        )

    # Incidents with annotations
    if inc_wh is not None:
        render_incidents_annotated(ax, inc_wh)

    # Region labels
    add_region_label(ax, -59, -52, "Patagonian Shelf\nSquid Grounds", fontsize=10, color="#ccddee")
    add_region_label(ax, -92, 2, "Gal\u00e1pagos\nMarine Reserve", fontsize=10, color="#ccddee")
    add_region_label(ax, -170, -10, "American\nSamoa", fontsize=9, color="#ccddee")
    add_region_label(ax, -157, 22, "Hawai\u02bbi", fontsize=9, color="#ccddee")
    add_region_label(ax, -85, -18, "Peru\nEEZ", fontsize=8)
    add_region_label(ax, -80, -35, "Chile\nEEZ", fontsize=8)

    # Year legend
    from src.maps.styles import YEAR_LABELS
    year_patches = [mpatches.Patch(color=c, label=YEAR_LABELS[y])
                    for y, c in YEAR_COLORS.items()]
    # Incident legend
    inc_handles = []
    for cat, style in INCIDENT_STYLES.items():
        h = mlines.Line2D([], [], color=style["color"], marker=style["marker"],
                          linestyle="None", markersize=8, markeredgecolor="white",
                          markeredgewidth=0.8, label=style["label"])
        inc_handles.append(h)

    # AIS gap handle
    gap_handle = mlines.Line2D([], [], color="#88ccff", marker="o",
                               linestyle="None", markersize=5, alpha=0.5,
                               label="AIS Disabling Event")

    all_handles = year_patches + [gap_handle] + inc_handles
    leg = ax.legend(
        handles=all_handles, title="Layers",
        loc="upper left", fontsize=7.5, title_fontsize=8.5,
        facecolor="#0d1b2a", edgecolor="#333355",
        labelcolor=TEXT_PRIMARY, framealpha=0.9,
    )
    leg.get_title().set_color(TEXT_PRIMARY)

    # Title
    fig.text(
        0.5, 0.96,
        "Chinese DWF Fleet in the Western Hemisphere 2022\u20132025",
        ha="center", va="top", fontsize=22, fontweight="bold",
        fontfamily=FONT_FAMILY, color=TEXT_PRIMARY,
    )
    fig.text(
        0.5, 0.94,
        "Fishing effort by year  \u2022  AIS disabling events  \u2022  "
        "Documented enforcement incidents  \u2022  EEZ boundaries (dashed)",
        ha="center", va="top", fontsize=10,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY,
    )
    fig.text(
        0.02, 0.01,
        "Sources: Global Fishing Watch (CC BY-SA 4.0), Marine Regions EEZ, "
        "curated incident reports",
        ha="left", va="bottom", fontsize=CAVEAT_FONTSIZE,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY,
    )

    out = config.STATIC_OUTPUT_DIR / "map2_western_hemisphere.png"
    fig.savefig(out, dpi=300, bbox_inches="tight",
                facecolor=fig.get_facecolor(), pad_inches=0.4)
    plt.close(fig)
    print(f"  Saved: {out}")


# =========================================================================
# MAP 3: Western Pacific / Indo-Pacific
# =========================================================================

def render_indo_pacific_map():
    """Western Pacific and Indian Ocean: SE Asia, Korea, W Africa, Indian Ocean."""
    print("\n=== Map 3: Indo-Pacific & West Africa ===")

    effort = pd.read_parquet(config.PROCESSED_DIR / "china_dwf_effort.parquet")
    gaps = None
    gap_path = config.PROCESSED_DIR / "ais_gaps_intentional.parquet"
    if gap_path.exists():
        gaps = pd.read_parquet(gap_path)

    from src.data.process_incidents import load_incidents
    try:
        incidents = load_incidents()
    except FileNotFoundError:
        incidents = None

    # Extent: West Africa through Western Pacific
    extent = [-25, 180, -50, 50]
    effort_ip = effort[(effort["lon"] >= extent[0]) & (effort["lon"] <= extent[1]) &
                       (effort["lat"] >= extent[2]) & (effort["lat"] <= extent[3])]
    print(f"  Effort cells in view: {len(effort_ip):,}")

    if incidents is not None:
        inc_ip = incidents[(incidents["lon"] >= extent[0]) & (incidents["lon"] <= extent[1]) &
                          (incidents["lat"] >= extent[2]) & (incidents["lat"] <= extent[3])]
    else:
        inc_ip = None

    if gaps is not None:
        gaps_ip = gaps[(gaps["off_lon"] >= extent[0]) & (gaps["off_lon"] <= extent[1]) &
                       (gaps["off_lat"] >= extent[2]) & (gaps["off_lat"] <= extent[3])]
    else:
        gaps_ip = None

    fig = plt.figure(figsize=(24, 14), facecolor=OCEAN_COLOR)
    ax = fig.add_subplot(1, 1, 1, projection=PLATE_CARREE)

    render_basemap(ax, extent=extent)
    render_eez(ax, highlight_countries=["KOR", "JPN", "PHL", "VNM", "IDN",
                                         "GHA", "CIV", "GIN", "VUT", "FJI"])

    # Effort by year
    from src.maps.styles import YEAR_COLORS, EFFORT_ALPHA_MIN, EFFORT_ALPHA_MAX, YEAR_LABELS
    for year in sorted(effort_ip["year"].unique()):
        if year not in YEAR_COLORS:
            continue
        yd = effort_ip[effort_ip["year"] == year]
        hours = yd["fishing_hours"].values
        log_h = np.log1p(hours)
        p95 = np.percentile(log_h, 95) if len(log_h) > 0 else 1
        if p95 == 0:
            p95 = 1
        norm = np.clip(log_h / p95, 0, 1)
        alphas = EFFORT_ALPHA_MIN + (EFFORT_ALPHA_MAX - EFFORT_ALPHA_MIN) * (norm ** 2)
        rgb = mcolors.to_rgb(YEAR_COLORS[year])
        colors = np.column_stack([
            np.full(len(yd), rgb[0]), np.full(len(yd), rgb[1]),
            np.full(len(yd), rgb[2]), alphas,
        ])
        ax.scatter(
            yd["lon"].values, yd["lat"].values,
            c=colors, s=0.6, transform=PLATE_CARREE,
            rasterized=True, zorder=2,
        )

    # AIS gaps
    if gaps_ip is not None and len(gaps_ip) > 0:
        ax.scatter(
            gaps_ip["off_lon"].values, gaps_ip["off_lat"].values,
            c="#88ccff", s=3, alpha=0.18,
            transform=PLATE_CARREE, rasterized=True, zorder=3,
        )

    # Incidents with annotations
    if inc_ip is not None:
        render_incidents_annotated(ax, inc_ip)

    # Region labels
    add_region_label(ax, 125, 35, "Yellow Sea /\nKorean EEZ", fontsize=9, color="#ccddee")
    add_region_label(ax, 115, 12, "South\nChina Sea", fontsize=9, color="#ccddee")
    add_region_label(ax, -5, 8, "Gulf of\nGuinea", fontsize=9, color="#ccddee")
    add_region_label(ax, 60, -15, "Indian\nOcean", fontsize=10, color="#ccddee")
    add_region_label(ax, 145, -5, "Papua New\nGuinea", fontsize=8)
    add_region_label(ax, 168, -17, "Vanuatu", fontsize=8, color="#ccddee")
    add_region_label(ax, 155, 40, "N. Pacific\nSquid Grounds", fontsize=9)

    # Legend
    year_patches = [mpatches.Patch(color=c, label=YEAR_LABELS[y])
                    for y, c in YEAR_COLORS.items()]
    inc_handles = []
    for cat, style in INCIDENT_STYLES.items():
        h = mlines.Line2D([], [], color=style["color"], marker=style["marker"],
                          linestyle="None", markersize=8, markeredgecolor="white",
                          markeredgewidth=0.8, label=style["label"])
        inc_handles.append(h)
    gap_handle = mlines.Line2D([], [], color="#88ccff", marker="o",
                               linestyle="None", markersize=5, alpha=0.5,
                               label="AIS Disabling Event")

    all_handles = year_patches + [gap_handle] + inc_handles
    leg = ax.legend(
        handles=all_handles, title="Layers",
        loc="lower left", fontsize=7.5, title_fontsize=8.5,
        facecolor="#0d1b2a", edgecolor="#333355",
        labelcolor=TEXT_PRIMARY, framealpha=0.9,
    )
    leg.get_title().set_color(TEXT_PRIMARY)

    # Title
    fig.text(
        0.5, 0.96,
        "Chinese DWF Fleet: Indo-Pacific & West Africa 2022\u20132025",
        ha="center", va="top", fontsize=22, fontweight="bold",
        fontfamily=FONT_FAMILY, color=TEXT_PRIMARY,
    )
    fig.text(
        0.5, 0.94,
        "Fishing effort by year  \u2022  AIS disabling events  \u2022  "
        "Documented enforcement incidents  \u2022  EEZ boundaries (dashed)",
        ha="center", va="top", fontsize=10,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY,
    )
    fig.text(
        0.02, 0.01,
        "Sources: Global Fishing Watch (CC BY-SA 4.0), Marine Regions EEZ, "
        "curated incident reports",
        ha="left", va="bottom", fontsize=CAVEAT_FONTSIZE,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY,
    )

    out = config.STATIC_OUTPUT_DIR / "map3_indo_pacific.png"
    fig.savefig(out, dpi=300, bbox_inches="tight",
                facecolor=fig.get_facecolor(), pad_inches=0.4)
    plt.close(fig)
    print(f"  Saved: {out}")


if __name__ == "__main__":
    render_seasonal_map()
    render_western_hemisphere_map()
    render_indo_pacific_map()
    print("\n=== All three maps rendered ===")
