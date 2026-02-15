"""
Three publication-quality maps of China's DWF fleet:
  1. Seasonal movement (global, 1-degree grid colored by peak month)
  2. Western Hemisphere (Americas + Hawaii) — heatmap + incident callouts
  3. Western Pacific / Indo-Pacific — heatmap + incident callouts

Design: effort rendered as smooth heatmap (background context), incidents
and EEZ boundaries as the narrative focal points (prominent annotations).
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

# ── Month color ramp ──────────────────────────────────────────────────────
MONTH_COLORS = {
    1: "#4575b4",  2: "#74add1",  3: "#abd9e9",  4: "#66c2a5",
    5: "#3cb44b",  6: "#fee090",  7: "#fdae61",  8: "#f46d43",
    9: "#d73027",  10: "#a50026", 11: "#8e4585", 12: "#5e4fa2",
}
MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

# ── Text styling ──────────────────────────────────────────────────────────
TEXT_OUTLINE = [pe.withStroke(linewidth=3, foreground="#0a1628")]

# ── Effort heatmap colormap: ocean-dark -> amber -> cream ─────────────────
EFFORT_CMAP = LinearSegmentedColormap.from_list("dwf_effort", [
    "#0a1628",  # invisible on ocean background
    "#1c1200",  # very dark brown
    "#3d2200",  # dark brown
    "#6b3a00",  # medium brown
    "#a05500",  # orange-brown
    "#cc7700",  # orange
    "#e8a530",  # amber
    "#fff0c0",  # cream
])
EFFORT_CMAP.set_bad(color=(0, 0, 0, 0))  # fully transparent for cartopy wrapping


# =========================================================================
# Data helpers
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


def grid_effort(df, resolution=0.5, extent=None):
    """
    Aggregate effort into a regular grid for pcolormesh rendering.

    Returns (lon_edges, lat_edges, grid_values).
    lon_edges has shape (N+1,), lat_edges has shape (M+1,), grid has shape (M, N).
    """
    d = df.copy()
    if extent:
        d = d[(d["lon"] >= extent[0]) & (d["lon"] <= extent[1]) &
              (d["lat"] >= extent[2]) & (d["lat"] <= extent[3])]

    if len(d) == 0:
        return None, None, None

    # Snap to grid centers
    d["grid_lat"] = (d["lat"] / resolution).round() * resolution
    d["grid_lon"] = (d["lon"] / resolution).round() * resolution

    gridded = d.groupby(["grid_lat", "grid_lon"])["fishing_hours"].sum().reset_index()

    lat_min = gridded["grid_lat"].min()
    lat_max = gridded["grid_lat"].max()
    lon_min = gridded["grid_lon"].min()
    lon_max = gridded["grid_lon"].max()

    # Cell centers and edges
    lat_centers = np.arange(lat_min, lat_max + resolution * 0.1, resolution)
    lon_centers = np.arange(lon_min, lon_max + resolution * 0.1, resolution)
    lat_edges = np.concatenate([lat_centers - resolution / 2,
                                [lat_centers[-1] + resolution / 2]])
    lon_edges = np.concatenate([lon_centers - resolution / 2,
                                [lon_centers[-1] + resolution / 2]])

    n_lat = len(lat_centers)
    n_lon = len(lon_centers)
    grid = np.full((n_lat, n_lon), np.nan)

    lat_idx = np.round((gridded["grid_lat"].values - lat_min) / resolution).astype(int)
    lon_idx = np.round((gridded["grid_lon"].values - lon_min) / resolution).astype(int)
    valid = (lat_idx >= 0) & (lat_idx < n_lat) & (lon_idx >= 0) & (lon_idx < n_lon)
    grid[lat_idx[valid], lon_idx[valid]] = gridded["fishing_hours"].values[valid]

    print(f"    Grid: {n_lat}x{n_lon} cells, "
          f"{np.count_nonzero(~np.isnan(grid)):,} non-empty")
    return lon_edges, lat_edges, grid


# =========================================================================
# Rendering components
# =========================================================================

def render_basemap(ax, extent=None):
    """Dark basemap with land, borders, graticules."""
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
    """EEZ boundaries — subtle background for all, prominent for key nations."""
    if eez_gdf is None:
        try:
            eez_gdf = _load_eez()
        except FileNotFoundError:
            return

    # All EEZ as faint background
    ax.add_geometries(
        eez_gdf.geometry, crs=PLATE_CARREE,
        facecolor="none", edgecolor=EEZ_LINE_COLOR,
        linewidth=0.3, alpha=0.12,
    )

    # Highlighted countries: bright, thick, dashed
    if highlight_countries:
        for iso in highlight_countries:
            country_eez = eez_gdf[eez_gdf["ISO_A3"] == iso]
            if len(country_eez) > 0:
                ax.add_geometries(
                    country_eez.geometry, crs=PLATE_CARREE,
                    facecolor="none", edgecolor="#55ccee",
                    linewidth=2.0, alpha=0.65, linestyle="--",
                )


def render_effort_heatmap(ax, effort_df, extent, resolution=0.5):
    """Render effort as a clean pcolormesh heatmap."""
    lon_edges, lat_edges, grid = grid_effort(
        effort_df, resolution=resolution, extent=extent
    )
    if grid is None:
        return

    # Log-transform and normalize to [0, 1]
    log_grid = np.log1p(np.where(np.isnan(grid), 0, grid))
    nonzero = log_grid[log_grid > 0]
    if len(nonzero) == 0:
        return
    p95 = np.percentile(nonzero, 95)
    if p95 == 0:
        p95 = 1
    normalized = np.clip(log_grid / p95, 0, 1)

    # Mask empty cells (will render as ocean background via set_bad)
    masked = np.ma.masked_where(np.isnan(grid) | (grid <= 0), normalized)

    ax.pcolormesh(
        lon_edges, lat_edges, masked,
        cmap=EFFORT_CMAP, vmin=0, vmax=1,
        transform=PLATE_CARREE, zorder=2,
        rasterized=True,
    )


def cluster_incidents(incidents_df, radius_deg=5.0):
    """
    Group nearby incidents into clusters for cleaner annotation.
    Returns list of cluster dicts with center position and summary text.
    """
    if incidents_df is None or len(incidents_df) == 0:
        return []

    clusters = []
    used = set()

    for idx, row in incidents_df.iterrows():
        if idx in used:
            continue

        group = [row]
        used.add(idx)

        for jdx, other in incidents_df.iterrows():
            if jdx in used:
                continue
            if (abs(row["lat"] - other["lat"]) < radius_deg and
                    abs(row["lon"] - other["lon"]) < radius_deg):
                group.append(other)
                used.add(jdx)

        center_lat = np.mean([r["lat"] for r in group])
        center_lon = np.mean([r["lon"] for r in group])

        if len(group) == 1:
            r = group[0]
            title = r.get("title", "")
            if len(title) > 48:
                title = title[:45] + "..."
            summary = title
        else:
            region = group[0].get("country_affected", "Region")
            n = len(group)
            lines = [f"{region}: {n} incidents"]
            for r in group[:3]:
                t = r.get("title", "")
                if len(t) > 38:
                    t = t[:35] + "..."
                lines.append(f"\u2022 {t}")
            if len(group) > 3:
                lines.append(f"\u2022 ...and {len(group) - 3} more")
            summary = "\n".join(lines)

        clusters.append({
            "lat": center_lat,
            "lon": center_lon,
            "incidents": group,
            "summary": summary,
            "n_incidents": len(group),
        })

    return clusters


def render_incidents_clustered(ax, incidents_df, manual_offsets=None):
    """
    Plot incident markers + clustered boxed annotations.

    manual_offsets: optional dict {cluster_index: (x_pts, y_pts)} to override
                    auto-positioning for specific clusters.
    """
    if incidents_df is None or len(incidents_df) == 0:
        return

    # Plot all individual markers
    for _, row in incidents_df.iterrows():
        cat = row["category"]
        style = INCIDENT_STYLES.get(cat, INCIDENT_STYLES["eez_violation"])
        ax.scatter(
            row["lon"], row["lat"],
            c=style["color"], marker=style["marker"],
            s=style["size"] * 1.5, edgecolors="white", linewidths=1.5,
            transform=PLATE_CARREE, zorder=10,
        )

    # Cluster and add boxed annotations
    clusters = cluster_incidents(incidents_df, radius_deg=5.0)

    default_offsets = [
        (55, 45), (-65, 50), (60, -50), (-60, -45),
        (70, 15), (-70, 15), (45, 60), (-50, -60),
    ]

    for i, cluster in enumerate(clusters):
        offset = default_offsets[i % len(default_offsets)]
        if manual_offsets and i in manual_offsets:
            offset = manual_offsets[i]

        ax.annotate(
            cluster["summary"],
            xy=(cluster["lon"], cluster["lat"]),
            xytext=offset,
            textcoords="offset points",
            fontsize=7.5,
            fontfamily=FONT_FAMILY,
            color=TEXT_PRIMARY,
            linespacing=1.4,
            bbox=dict(
                boxstyle="round,pad=0.4",
                facecolor="#0d1b2a",
                edgecolor="#556677",
                alpha=0.9,
            ),
            xycoords=PLATE_CARREE._as_mpl_transform(ax),
            zorder=12,
            arrowprops=dict(
                arrowstyle="-|>",
                color="#8899aa",
                linewidth=1.0,
                connectionstyle="arc3,rad=0.15",
            ),
        )


def add_region_label(ax, lon, lat, text, fontsize=9, color=TEXT_SECONDARY):
    """Region label with outline for readability over dark background."""
    ax.text(
        lon, lat, text,
        transform=PLATE_CARREE,
        fontsize=fontsize, fontfamily=FONT_FAMILY,
        color=color, ha="center", va="center",
        style="italic",
        path_effects=TEXT_OUTLINE,
        zorder=8,
    )


def add_effort_colorbar(fig, label="Fishing Effort Intensity"):
    """Add a horizontal effort colorbar at the bottom of the figure."""
    cbar_ax = fig.add_axes([0.12, 0.065, 0.25, 0.012])
    norm = plt.Normalize(0, 1)
    sm = plt.cm.ScalarMappable(cmap=EFFORT_CMAP, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal")
    cbar.set_label(label, fontsize=8, color=TEXT_PRIMARY, fontfamily=FONT_FAMILY)
    cbar.set_ticks([0, 0.5, 1])
    cbar.set_ticklabels(["Low", "Medium", "High"])
    cbar.ax.tick_params(labelsize=7, colors=TEXT_PRIMARY)
    return cbar


def add_incident_legend(ax, loc="upper left", bbox=None):
    """Add a legend for incident marker types + EEZ boundaries."""
    handles = []
    for cat, style in INCIDENT_STYLES.items():
        if cat == "transshipment":
            continue
        h = mlines.Line2D(
            [], [], color=style["color"], marker=style["marker"],
            linestyle="None", markersize=9, markeredgecolor="white",
            markeredgewidth=1.0, label=style["label"],
        )
        handles.append(h)
    handles.append(mlines.Line2D(
        [], [], color="#55ccee", linestyle="--",
        linewidth=1.5, label="National EEZ",
    ))

    kwargs = dict(
        handles=handles, title="Incidents & Boundaries",
        loc=loc, fontsize=8, title_fontsize=9,
        facecolor="#0d1b2a", edgecolor="#333355",
        labelcolor=TEXT_PRIMARY, framealpha=0.92,
    )
    if bbox:
        kwargs["bbox_to_anchor"] = bbox
    leg = ax.legend(**kwargs)
    leg.get_title().set_color(TEXT_PRIMARY)
    return leg


# =========================================================================
# MAP 1: Seasonal Movement (Global)
# =========================================================================

def render_seasonal_map():
    """Global map: 1-degree grid colored by peak fishing month."""
    print("=== Map 1: Seasonal Movement ===")

    # Load raw CSVs (need monthly resolution)
    frames = []
    for year in config.YEARS:
        f = config.GFW_EFFORT_DIR / f"china_effort_{year}.csv"
        if f.exists():
            df = pd.read_csv(f)
            df.columns = ["lat", "lon", "time_range", "flag", "geartype",
                          "vessel_count", "fishing_hours"]
            df = df[~((df["lat"] >= 18) & (df["lat"] <= 42) &
                      (df["lon"] >= 105) & (df["lon"] <= 130))]
            df["month"] = df["time_range"].str[5:7].astype(int)
            frames.append(df)

    effort = pd.concat(frames, ignore_index=True)

    # Aggregate to 1-degree grid
    res = 1.0
    effort["grid_lat"] = (effort["lat"] / res).round() * res
    effort["grid_lon"] = (effort["lon"] / res).round() * res

    monthly_grid = effort.groupby(
        ["grid_lat", "grid_lon", "month"], as_index=False
    ).agg(fishing_hours=("fishing_hours", "sum"))

    # Dominant month per cell
    idx = monthly_grid.groupby(["grid_lat", "grid_lon"])["fishing_hours"].idxmax()
    dominant = monthly_grid.loc[idx].copy()

    # Total effort per cell (for brightness)
    totals = effort.groupby(
        ["grid_lat", "grid_lon"]
    )["fishing_hours"].sum().reset_index(name="total_hours")
    dominant = dominant.merge(totals, on=["grid_lat", "grid_lon"])
    print(f"  {len(dominant):,} grid cells at {res}\u00b0 resolution")

    # ── Render ──
    projection = ccrs.Robinson(central_longitude=180)
    fig = plt.figure(figsize=(24, 13), facecolor=OCEAN_COLOR)
    ax = fig.add_subplot(1, 1, 1, projection=projection)

    render_basemap(ax)
    render_eez(ax)

    # Alpha from effort intensity
    log_h = np.log1p(dominant["total_hours"].values)
    p95 = np.percentile(log_h, 95)
    if p95 == 0:
        p95 = 1
    norm = np.clip(log_h / p95, 0, 1)
    alphas = 0.15 + 0.75 * (norm ** 1.2)

    # Plot grid cells as colored squares
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

    # Region labels
    add_region_label(ax, -58, -52, "Patagonian\nShelf", fontsize=10)
    add_region_label(ax, -92, -5, "Gal\u00e1pagos", fontsize=10)
    add_region_label(ax, -170, -14, "American\nSamoa", fontsize=9)
    add_region_label(ax, -155, 24, "Hawai\u02bbi", fontsize=9)
    add_region_label(ax, 55, -22, "Indian\nOcean", fontsize=10)
    add_region_label(ax, -8, 7, "Gulf of\nGuinea", fontsize=9)
    add_region_label(ax, 152, 38, "N. Pacific\nSquid Grounds", fontsize=9)
    add_region_label(ax, 125, -8, "SE Asia /\nCoral Triangle", fontsize=9)
    add_region_label(ax, 127, 37, "Korean\nWaters", fontsize=8)

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

    # Titles
    fig.text(
        0.5, 0.96,
        "China\u2019s Distant Water Fleet: Seasonal Fishing Patterns 2022\u20132025",
        ha="center", va="top", fontsize=24, fontweight="bold",
        fontfamily=FONT_FAMILY, color=TEXT_PRIMARY,
    )
    fig.text(
        0.5, 0.935,
        "Each cell colored by peak fishing month  \u2022  "
        "Brightness shows effort intensity  \u2022  1\u00b0 grid",
        ha="center", va="top", fontsize=12,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY,
    )
    fig.text(
        0.02, 0.01,
        "Source: Global Fishing Watch 4Wings API (CC BY-SA 4.0)  \u2022  "
        "Robinson projection centered on 180\u00b0",
        ha="left", va="bottom", fontsize=CAVEAT_FONTSIZE,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY,
    )
    fig.text(
        0.98, 0.01,
        "Note: AIS-broadcasting vessels only (~50% of fleet). "
        "China domestic waters excluded.",
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
    """Americas + Hawaii: heatmap background, prominent incident callouts."""
    print("\n=== Map 2: Western Hemisphere ===")

    effort = pd.read_parquet(config.PROCESSED_DIR / "china_dwf_effort.parquet")

    from src.data.process_incidents import load_incidents
    try:
        incidents = load_incidents()
    except FileNotFoundError:
        incidents = None

    extent = [-180, -30, -60, 35]

    inc_wh = None
    if incidents is not None:
        inc_wh = incidents[
            (incidents["lon"] >= extent[0]) & (incidents["lon"] <= extent[1]) &
            (incidents["lat"] >= extent[2]) & (incidents["lat"] <= extent[3])
        ]

    # ── Render ──
    fig = plt.figure(figsize=(20, 16), facecolor=OCEAN_COLOR)
    ax = fig.add_subplot(1, 1, 1, projection=PLATE_CARREE)

    render_basemap(ax, extent=extent)
    render_eez(ax, highlight_countries=["ARG", "ECU", "USA", "PER", "CHL", "BRA"])

    # Effort heatmap
    print("  Rendering effort heatmap...")
    render_effort_heatmap(ax, effort, extent=extent, resolution=0.5)

    # Incident annotations
    if inc_wh is not None and len(inc_wh) > 0:
        print(f"  Annotating {len(inc_wh)} incidents...")
        render_incidents_clustered(ax, inc_wh)

    # Region labels
    add_region_label(ax, -65, -55, "Patagonian Shelf\nSquid Grounds",
                     fontsize=11, color="#ccddee")
    add_region_label(ax, -98, 6, "Gal\u00e1pagos\nMarine Reserve",
                     fontsize=11, color="#ccddee")
    add_region_label(ax, -170, -5, "American\nSamoa", fontsize=9, color="#ccddee")
    add_region_label(ax, -157, 28, "Hawai\u02bbi", fontsize=10, color="#ccddee")
    add_region_label(ax, -85, -24, "Peru EEZ", fontsize=8)
    add_region_label(ax, -80, -40, "Chile EEZ", fontsize=8)

    # Legend
    add_effort_colorbar(fig)
    add_incident_legend(ax, loc="upper left")

    # Titles
    fig.text(
        0.5, 0.97,
        "Chinese DWF Fleet in the Western Hemisphere 2022\u20132025",
        ha="center", va="top", fontsize=22, fontweight="bold",
        fontfamily=FONT_FAMILY, color=TEXT_PRIMARY,
    )
    fig.text(
        0.5, 0.95,
        "Fishing effort intensity  \u2022  Documented enforcement "
        "incidents  \u2022  EEZ boundaries (dashed)",
        ha="center", va="top", fontsize=10,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY,
    )
    fig.text(
        0.02, 0.01,
        "Sources: Global Fishing Watch (CC BY-SA 4.0), EEZ boundaries, "
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
# MAP 3: Indo-Pacific & West Africa
# =========================================================================

def render_indo_pacific_map():
    """Western Pacific, Indian Ocean, West Africa: heatmap + incidents."""
    print("\n=== Map 3: Indo-Pacific & West Africa ===")

    effort = pd.read_parquet(config.PROCESSED_DIR / "china_dwf_effort.parquet")

    from src.data.process_incidents import load_incidents
    try:
        incidents = load_incidents()
    except FileNotFoundError:
        incidents = None

    # Tighter extent: West Africa coast through western Pacific
    extent = [-20, 175, -42, 48]

    inc_ip = None
    if incidents is not None:
        inc_ip = incidents[
            (incidents["lon"] >= extent[0]) & (incidents["lon"] <= extent[1]) &
            (incidents["lat"] >= extent[2]) & (incidents["lat"] <= extent[3])
        ]

    # ── Render ──
    fig = plt.figure(figsize=(22, 13), facecolor=OCEAN_COLOR)
    ax = fig.add_subplot(1, 1, 1, projection=PLATE_CARREE)

    render_basemap(ax, extent=extent)
    render_eez(ax, highlight_countries=[
        "KOR", "JPN", "PHL", "VNM", "IDN",
        "GHA", "CIV", "GIN", "VUT", "FJI",
    ])

    # Effort heatmap
    print("  Rendering effort heatmap...")
    render_effort_heatmap(ax, effort, extent=extent, resolution=0.5)

    # Incident annotations
    if inc_ip is not None and len(inc_ip) > 0:
        print(f"  Annotating {len(inc_ip)} incidents...")
        render_incidents_clustered(ax, inc_ip)

    # Region labels
    add_region_label(ax, 126, 38, "Yellow Sea /\nKorean EEZ",
                     fontsize=10, color="#ccddee")
    add_region_label(ax, 115, 10, "South\nChina Sea",
                     fontsize=10, color="#ccddee")
    add_region_label(ax, -6, 12, "Gulf of\nGuinea",
                     fontsize=10, color="#ccddee")
    add_region_label(ax, 60, -20, "Indian\nOcean",
                     fontsize=11, color="#ccddee")
    add_region_label(ax, 145, -8, "Papua New\nGuinea", fontsize=8)
    add_region_label(ax, 168, -20, "Vanuatu",
                     fontsize=9, color="#ccddee")
    add_region_label(ax, 152, 43, "N. Pacific\nSquid Grounds", fontsize=9)

    # Legend
    add_effort_colorbar(fig)
    add_incident_legend(ax, loc="lower left", bbox=(0.28, 0.0))

    # Titles
    fig.text(
        0.5, 0.97,
        "Chinese DWF Fleet: Indo-Pacific & West Africa 2022\u20132025",
        ha="center", va="top", fontsize=22, fontweight="bold",
        fontfamily=FONT_FAMILY, color=TEXT_PRIMARY,
    )
    fig.text(
        0.5, 0.95,
        "Fishing effort intensity  \u2022  Documented enforcement "
        "incidents  \u2022  EEZ boundaries (dashed)",
        ha="center", va="top", fontsize=10,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY,
    )
    fig.text(
        0.02, 0.01,
        "Sources: Global Fishing Watch (CC BY-SA 4.0), EEZ boundaries, "
        "curated incident reports",
        ha="left", va="bottom", fontsize=CAVEAT_FONTSIZE,
        fontfamily=FONT_FAMILY, color=TEXT_SECONDARY,
    )

    out = config.STATIC_OUTPUT_DIR / "map3_indo_pacific.png"
    fig.savefig(out, dpi=300, bbox_inches="tight",
                facecolor=fig.get_facecolor(), pad_inches=0.4)
    plt.close(fig)
    print(f"  Saved: {out}")


# =========================================================================

if __name__ == "__main__":
    render_seasonal_map()
    render_western_hemisphere_map()
    render_indo_pacific_map()
    print("\n=== All three maps rendered ===")
