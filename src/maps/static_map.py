"""
Publication-quality static map of Chinese DWF fleet activity.

Uses matplotlib + cartopy with Pacific-centered Robinson projection.
Renders to PNG (300 DPI), PDF, and SVG.
"""

import sys
from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config
from src.maps.styles import (
    OCEAN_COLOR, LAND_COLOR, COUNTRY_BORDER_COLOR,
    EEZ_LINE_COLOR, EEZ_LINE_ALPHA,
    GRATICULE_COLOR, TEXT_PRIMARY, TEXT_SECONDARY,
    YEAR_COLORS, YEAR_LABELS,
    INCIDENT_STYLES,
    EFFORT_ALPHA_MIN, EFFORT_ALPHA_MAX, EFFORT_POINT_SIZE,
    FONT_FAMILY, TITLE_FONTSIZE, SUBTITLE_FONTSIZE,
    LABEL_FONTSIZE, LEGEND_FONTSIZE, ANNOTATION_FONTSIZE, CAVEAT_FONTSIZE,
    MAP_DPI, MAP_FIGSIZE,
    INSET_GALAPAGOS, INSET_ARGENTINA, INSET_SAMOA,
)


# Projections
ROBINSON_PACIFIC = ccrs.Robinson(central_longitude=config.MAP_CENTER_LON)
PLATE_CARREE = ccrs.PlateCarree()


def _load_natural_earth(name: str) -> gpd.GeoDataFrame:
    """Load a Natural Earth shapefile by dataset name."""
    d = config.NATURAL_EARTH_DIR / name
    shp_files = list(d.glob("*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"No shapefile in {d}")
    return gpd.read_file(shp_files[0])


def render_basemap(ax):
    """Render the dark basemap on a cartopy axes."""
    # Ocean background
    ax.set_facecolor(OCEAN_COLOR)

    # Land
    land = _load_natural_earth("land")
    ax.add_geometries(
        land.geometry,
        crs=PLATE_CARREE,
        facecolor=LAND_COLOR,
        edgecolor=COUNTRY_BORDER_COLOR,
        linewidth=0.3,
    )

    # Country borders
    countries = _load_natural_earth("countries")
    ax.add_geometries(
        countries.geometry,
        crs=PLATE_CARREE,
        facecolor="none",
        edgecolor=COUNTRY_BORDER_COLOR,
        linewidth=0.2,
    )

    # Graticules
    graticules = _load_natural_earth("graticules")
    ax.add_geometries(
        graticules.geometry,
        crs=PLATE_CARREE,
        facecolor="none",
        edgecolor=GRATICULE_COLOR,
        linewidth=0.3,
    )

    ax.set_global()


def render_eez(ax, eez_gdf: gpd.GeoDataFrame | None = None):
    """Render EEZ boundaries as thin semi-transparent lines."""
    if eez_gdf is None:
        try:
            from src.utils.geo import load_eez
            eez_gdf = load_eez(simplify_tolerance=0.05)
        except FileNotFoundError:
            print("  EEZ data not available, skipping EEZ layer")
            return

    ax.add_geometries(
        eez_gdf.geometry,
        crs=PLATE_CARREE,
        facecolor="none",
        edgecolor=EEZ_LINE_COLOR,
        linewidth=0.4,
        alpha=EEZ_LINE_ALPHA,
    )


def render_effort(ax, effort_df: pd.DataFrame):
    """
    Render fishing effort as colored scatter points by year.

    Renders oldest year first so newer years paint on top.
    Uses aggressive alpha scaling so low-effort cells barely show
    and only high-effort hotspots are vivid.
    """
    if effort_df is None or len(effort_df) == 0:
        return

    # Detect column names
    lat_col = "lat" if "lat" in effort_df.columns else "grid_lat"
    lon_col = "lon" if "lon" in effort_df.columns else "grid_lon"

    # Use per-year percentile for alpha scaling (not global max)
    # This ensures each year's hotspots are visible
    for year in sorted(effort_df["year"].unique()):
        if year not in YEAR_COLORS:
            continue
        year_data = effort_df[effort_df["year"] == year]
        color = YEAR_COLORS[year]

        hours = year_data["fishing_hours"].values
        log_hours = np.log1p(hours)

        # Use 95th percentile as effective max to avoid outlier compression
        p95 = np.percentile(log_hours, 95)
        if p95 == 0:
            p95 = 1
        normalized = np.clip(log_hours / p95, 0, 1)

        # Quadratic curve: most points very faint, only hotspots bright
        alphas = EFFORT_ALPHA_MIN + (EFFORT_ALPHA_MAX - EFFORT_ALPHA_MIN) * (normalized ** 2)

        rgb = mcolors.to_rgb(color)
        colors = np.column_stack([
            np.full(len(year_data), rgb[0]),
            np.full(len(year_data), rgb[1]),
            np.full(len(year_data), rgb[2]),
            alphas,
        ])

        ax.scatter(
            year_data[lon_col].values,
            year_data[lat_col].values,
            c=colors,
            s=EFFORT_POINT_SIZE,
            transform=PLATE_CARREE,
            rasterized=True,
            zorder=2,
        )


def render_ais_gaps(ax, gaps_df: pd.DataFrame):
    """Render AIS gap off-positions as small translucent cyan dots."""
    if gaps_df is None or len(gaps_df) == 0:
        return

    # Use the off-position (where AIS was disabled)
    lat_col = "off_lat" if "off_lat" in gaps_df.columns else "lat"
    lon_col = "off_lon" if "off_lon" in gaps_df.columns else "lon"

    ax.scatter(
        gaps_df[lon_col].values,
        gaps_df[lat_col].values,
        c="#88ccff",
        s=3,
        alpha=0.15,
        transform=PLATE_CARREE,
        rasterized=True,
        zorder=3,
    )


def render_encounters(ax, enc_df: pd.DataFrame):
    """Render encounter events as small translucent purple dots."""
    if enc_df is None or len(enc_df) == 0:
        return

    # Separate transshipment (carrier involved) from fishing-fishing
    carrier = enc_df[enc_df["encounter_type"].isin(["carrier-fishing", "fishing-carrier"])]
    fishing = enc_df[enc_df["encounter_type"] == "fishing-fishing"]

    if len(fishing) > 0:
        ax.scatter(
            fishing["lon"].values, fishing["lat"].values,
            c="#6644aa", s=2, alpha=0.08,
            transform=PLATE_CARREE, rasterized=True, zorder=3,
        )
    if len(carrier) > 0:
        ax.scatter(
            carrier["lon"].values, carrier["lat"].values,
            c="#aa66cc", s=8, alpha=0.6,
            marker="h",
            transform=PLATE_CARREE, rasterized=True, zorder=4,
        )


def render_incidents(ax, incidents_df: pd.DataFrame):
    """Render incident markers with category-specific styling."""
    if incidents_df is None or len(incidents_df) == 0:
        return

    for cat, style in INCIDENT_STYLES.items():
        cat_data = incidents_df[incidents_df["category"] == cat]
        if len(cat_data) == 0:
            continue

        ax.scatter(
            cat_data["lon"].values,
            cat_data["lat"].values,
            c=style["color"],
            marker=style["marker"],
            s=style["size"],
            edgecolors="white",
            linewidths=1.0,
            transform=PLATE_CARREE,
            zorder=10,
            label=style["label"],
        )


def add_legend(fig, ax):
    """Add year color legend and incident category legend."""
    # Year legend
    year_patches = [
        mpatches.Patch(color=color, label=YEAR_LABELS[year])
        for year, color in YEAR_COLORS.items()
    ]
    year_legend = ax.legend(
        handles=year_patches,
        title="Year",
        loc="lower left",
        fontsize=LEGEND_FONTSIZE,
        title_fontsize=LEGEND_FONTSIZE + 1,
        facecolor="#0d1b2a",
        edgecolor="#333355",
        labelcolor=TEXT_PRIMARY,
        framealpha=0.9,
    )
    year_legend.get_title().set_color(TEXT_PRIMARY)
    ax.add_artist(year_legend)

    # Incident legend
    incident_handles = []
    for cat, style in INCIDENT_STYLES.items():
        handle = plt.scatter(
            [], [],
            c=style["color"],
            marker=style["marker"],
            s=style["size"] * 0.7,
            edgecolors="white",
            linewidths=0.5,
            label=style["label"],
        )
        incident_handles.append(handle)

    incident_legend = ax.legend(
        handles=incident_handles,
        title="Incidents",
        loc="upper left",
        fontsize=ANNOTATION_FONTSIZE,
        title_fontsize=ANNOTATION_FONTSIZE + 1,
        facecolor="#0d1b2a",
        edgecolor="#333355",
        labelcolor=TEXT_PRIMARY,
        framealpha=0.9,
    )
    incident_legend.get_title().set_color(TEXT_PRIMARY)
    ax.add_artist(incident_legend)


def add_annotations(fig, ax):
    """Add title, subtitle, source attribution, and caveats."""
    fig.text(
        0.5, 0.96,
        "China's Distant Water Fishing Fleet: Global Activity 2022\u20132025",
        ha="center", va="top",
        fontsize=TITLE_FONTSIZE,
        fontfamily=FONT_FAMILY,
        fontweight="bold",
        color=TEXT_PRIMARY,
    )
    fig.text(
        0.5, 0.935,
        "Fishing effort by year  \u2022  Documented incidents  \u2022  EEZ boundaries",
        ha="center", va="top",
        fontsize=SUBTITLE_FONTSIZE,
        fontfamily=FONT_FAMILY,
        color=TEXT_SECONDARY,
    )

    # Source attribution
    fig.text(
        0.02, 0.01,
        "Sources: Global Fishing Watch (CC BY-SA 4.0), Marine Regions EEZ v12, "
        "curated incident reports  \u2022  Robinson projection centered on 180\u00b0",
        ha="left", va="bottom",
        fontsize=CAVEAT_FONTSIZE,
        fontfamily=FONT_FAMILY,
        color=TEXT_SECONDARY,
    )

    # AIS caveat
    fig.text(
        0.98, 0.01,
        "Note: Only ~50% of China\u2019s DWF fleet broadcasts AIS. "
        "Actual fleet presence is likely substantially greater.",
        ha="right", va="bottom",
        fontsize=CAVEAT_FONTSIZE,
        fontfamily=FONT_FAMILY,
        color=TEXT_SECONDARY,
        style="italic",
    )


def create_inset(fig, bounds, extent, title, eez_gdf=None, effort_df=None, incidents_df=None):
    """
    Create an inset map at the given figure position.

    Args:
        bounds: [left, bottom, width, height] in figure coordinates
        extent: [lon_min, lon_max, lat_min, lat_max] in degrees
        title: Inset title string
    """
    ax_inset = fig.add_axes(bounds, projection=PLATE_CARREE)
    ax_inset.set_extent(extent, crs=PLATE_CARREE)

    # Render layers
    render_basemap(ax_inset)
    if eez_gdf is not None:
        render_eez(ax_inset, eez_gdf)
    if effort_df is not None:
        render_effort(ax_inset, effort_df)
    if incidents_df is not None:
        render_incidents(ax_inset, incidents_df)

    # Inset title
    ax_inset.set_title(
        title,
        fontsize=LABEL_FONTSIZE,
        fontfamily=FONT_FAMILY,
        color=TEXT_PRIMARY,
        pad=4,
    )

    # Border
    for spine in ax_inset.spines.values():
        spine.set_edgecolor(TEXT_SECONDARY)
        spine.set_linewidth(0.8)

    return ax_inset


def render_map(
    effort_df: pd.DataFrame | None = None,
    incidents_df: pd.DataFrame | None = None,
    gaps_df: pd.DataFrame | None = None,
    encounters_df: pd.DataFrame | None = None,
    eez_gdf: gpd.GeoDataFrame | None = None,
    output_prefix: str = "dwf_global_map",
):
    """
    Render the full publication-quality map.

    Args:
        effort_df: Processed fishing effort DataFrame
        incidents_df: Incident database DataFrame
        gaps_df: AIS gap (disabling) events DataFrame
        encounters_df: Encounter events DataFrame
        eez_gdf: EEZ boundary GeoDataFrame
        output_prefix: Filename prefix for output files
    """
    print("=== Rendering Static Map ===")

    fig = plt.figure(figsize=MAP_FIGSIZE, facecolor=OCEAN_COLOR)
    ax = fig.add_subplot(1, 1, 1, projection=ROBINSON_PACIFIC)

    # Basemap
    print("  Rendering basemap...")
    render_basemap(ax)

    # EEZ
    print("  Rendering EEZ boundaries...")
    render_eez(ax, eez_gdf)

    # Fishing effort
    if effort_df is not None:
        print(f"  Rendering fishing effort ({len(effort_df):,} cells)...")
        render_effort(ax, effort_df)

    # AIS gaps
    if gaps_df is not None:
        print(f"  Rendering {len(gaps_df):,} AIS gap events...")
        render_ais_gaps(ax, gaps_df)

    # Encounters
    if encounters_df is not None:
        print(f"  Rendering {len(encounters_df):,} encounter events...")
        render_encounters(ax, encounters_df)

    # Incidents
    if incidents_df is not None:
        print(f"  Rendering {len(incidents_df)} incidents...")
        render_incidents(ax, incidents_df)

    # Legend and annotations
    add_legend(fig, ax)
    add_annotations(fig, ax)

    # Inset maps
    print("  Rendering inset maps...")
    if effort_df is not None or incidents_df is not None:
        create_inset(
            fig, INSET_GALAPAGOS,
            [-95, -85, -5, 3],
            "Gal\u00e1pagos EEZ",
            eez_gdf=eez_gdf, effort_df=effort_df, incidents_df=incidents_df,
        )
        create_inset(
            fig, INSET_ARGENTINA,
            [-68, -52, -55, -35],
            "Argentine Patagonian Shelf",
            eez_gdf=eez_gdf, effort_df=effort_df, incidents_df=incidents_df,
        )
        create_inset(
            fig, INSET_SAMOA,
            [-178, -163, -20, -8],
            "American Samoa",
            eez_gdf=eez_gdf, effort_df=effort_df, incidents_df=incidents_df,
        )

    # Save
    config.STATIC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    png_path = config.STATIC_OUTPUT_DIR / f"{output_prefix}.png"
    print(f"  Saving PNG ({MAP_DPI} DPI)...")
    fig.savefig(png_path, dpi=MAP_DPI, bbox_inches="tight",
                facecolor=fig.get_facecolor(), pad_inches=0.5)
    print(f"  Saved: {png_path}")

    pdf_path = config.STATIC_OUTPUT_DIR / f"{output_prefix}.pdf"
    print(f"  Saving PDF...")
    fig.savefig(pdf_path, bbox_inches="tight",
                facecolor=fig.get_facecolor(), pad_inches=0.5)
    print(f"  Saved: {pdf_path}")

    plt.close(fig)
    print("  Done.")


def render_basemap_only():
    """Quick render of just the basemap for design review."""
    print("=== Rendering Basemap Preview ===")

    fig = plt.figure(figsize=(20, 11), facecolor=OCEAN_COLOR)
    ax = fig.add_subplot(1, 1, 1, projection=ROBINSON_PACIFIC)

    render_basemap(ax)
    add_annotations(fig, ax)

    config.STATIC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    preview_path = config.STATIC_OUTPUT_DIR / "basemap_preview.png"
    fig.savefig(preview_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor(), pad_inches=0.3)
    plt.close(fig)
    print(f"  Saved: {preview_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true",
                        help="Render basemap only for design review")
    parser.add_argument("--with-incidents", action="store_true",
                        help="Include incidents layer (no effort data)")
    args = parser.parse_args()

    if args.preview:
        render_basemap_only()
    elif args.with_incidents:
        from src.data.process_incidents import load_incidents
        try:
            incidents = load_incidents()
        except FileNotFoundError:
            incidents = None
        render_map(incidents_df=incidents)
    else:
        # Full render with all data layers
        effort = None
        effort_path = config.PROCESSED_DIR / "china_dwf_effort.parquet"
        if effort_path.exists():
            effort = pd.read_parquet(effort_path)

        gaps = None
        gaps_path = config.PROCESSED_DIR / "ais_gaps_intentional.parquet"
        if gaps_path.exists():
            gaps = pd.read_parquet(gaps_path)

        encounters = None
        enc_path = config.PROCESSED_DIR / "encounters.parquet"
        if enc_path.exists():
            encounters = pd.read_parquet(enc_path)

        from src.data.process_incidents import load_incidents
        try:
            incidents = load_incidents()
        except FileNotFoundError:
            incidents = None

        render_map(
            effort_df=effort,
            incidents_df=incidents,
            gaps_df=gaps,
            encounters_df=encounters,
        )
